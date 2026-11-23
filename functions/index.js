const functions = require("firebase-functions");
const admin = require("firebase-admin");
const { OpenAI } = require("openai");
const Anthropic = require("@anthropic-ai/sdk");
const { GoogleGenerativeAI } = require("@google/generative-ai");

admin.initializeApp();
const db = admin.firestore();

exports.generateSecureReply = functions
  .runWith({ secrets: ["OPENAI_API_KEY"] })
  .https.onCall(async (data, context) => {
    // 1. Authenticate user
    if (!context.auth) {
      throw new functions.https.HttpsError("unauthenticated", "User must be logged in.");
    }
    const userId = context.auth.uid;

    // 2. Fetch User Balance
    const userRef = db.collection("users").doc(userId);
    const userDoc = await userRef.get();
    
    if (!userDoc.exists) {
      throw new functions.https.HttpsError("not-found", "User document not found.");
    }

    const currentBalance = userDoc.data().balance || 0;
    if (currentBalance < 15) {
      throw new functions.https.HttpsError("resource-exhausted", "Minimum balance of ₹15 is required for AI generation. Please top up your account.");
    }

    const provider = data.provider || "openai";
    // Hard cap input text sizes to prevent token exhaustion and negative balances
    const promptInstruction = (data.prompt || "Draft a professional reply to the following document based on its contents.").substring(0, 1000);
    const rawRedactedText = data.redacted_text || "";
    const redactedText = rawRedactedText.substring(0, 10000);

    if (!redactedText) {
      throw new functions.https.HttpsError("invalid-argument", "redacted_text is required.");
    }

    const systemMsg = "You are a helpful and professional assistant. IMPORTANT: When generating your reply, DO NOT use generic placeholders like [Your Name], [Client Name], or [GSTIN]. Instead, you MUST use the specific names, IDs, and entities found in the document.";
    const userMsg = `${promptInstruction}\n\nDocument:\n${redactedText}`;

    let replyContent = "";
    let baseCost = 0;

    try {
      if (provider === "google") {
        const genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);
        // Explicitly limit maxOutputTokens to 1000 to cap costs
        const model = genAI.getGenerativeModel({ model: "gemini-pro", generationConfig: { maxOutputTokens: 1000 } });
        const result = await model.generateContent(`${systemMsg}\n\n${userMsg}`);
        const response = await result.response;
        replyContent = response.text();
        
        // Approximate cost for Gemini Pro (per 1k tokens: $0.0005 input, $0.0015 output)
        // Since Gemini JS SDK doesn't consistently return token counts easily, we estimate based on characters (roughly 4 chars = 1 token)
        const estInputTokens = (systemMsg.length + userMsg.length) / 4;
        const estOutputTokens = replyContent.length / 4;
        baseCost = (estInputTokens / 1000 * 0.0005) + (estOutputTokens / 1000 * 0.0015);
        
      } else if (provider === "anthropic") {
        const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
        const message = await anthropic.messages.create({
          model: "claude-3-opus-20240229",
          max_tokens: 1000,
          temperature: 0.7,
          system: systemMsg,
          messages: [{ role: "user", content: userMsg }]
        });
        replyContent = message.content[0].text;
        
        const inputTokens = message.usage.input_tokens;
        const outputTokens = message.usage.output_tokens;
        // Claude 3 Opus prices: $15 / 1M input, $75 / 1M output
        baseCost = (inputTokens / 1000000 * 15.0) + (outputTokens / 1000000 * 75.0);

      } else {
        // Default to OpenAI
        const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
        const completion = await openai.chat.completions.create({
          model: "gpt-4o-mini",
          messages: [
            { role: "system", content: systemMsg },
            { role: "user", content: userMsg }
          ],
          max_tokens: 1000,
          temperature: 0.7
        });
        
        replyContent = completion.choices[0].message.content;
        
        const promptTokens = completion.usage.prompt_tokens;
        const completionTokens = completion.usage.completion_tokens;
        // gpt-4o-mini prices: $0.00015 / 1k input, $0.0006 / 1k output
        baseCost = (promptTokens / 1000 * 0.00015) + (completionTokens / 1000 * 0.0006);
      }

      // Calculate total charge with 30% markup and convert USD to INR (approx 100 INR/USD)
      const markup = 1.30;
      const usdToInr = 100.0;
      let totalCharge = baseCost * markup * usdToInr;
      
      // Ensure minimum charge of 15 Paise (0.15 INR)
      if (totalCharge < 0.15) {
          totalCharge = 0.15;
      }

      // Ensure we don't deduct if there's an error calculating cost (safety net)
      if (totalCharge > 0) {
        await userRef.update({
          balance: admin.firestore.FieldValue.increment(-totalCharge)
        });
        
        await db.collection("transactions").add({
          uid: userId,
          type: "DEBIT",
          description: "AI Generation",
          amount: -totalCharge,
          created_at: admin.firestore.FieldValue.serverTimestamp()
        });
      }

      return {
        success: true,
        reply: replyContent,
        costCharged: totalCharge
      };

    } catch (error) {
      console.error("AI Generation Error:", error);
      throw new functions.https.HttpsError("internal", error.message);
    }
  });

exports.generateSmartRenameBatch = functions
  .runWith({ secrets: ["OPENAI_API_KEY"] })
  .https.onCall(async (data, context) => {
    // 1. Authenticate user
    if (!context.auth) {
      throw new functions.https.HttpsError("unauthenticated", "User must be logged in.");
    }
    const userId = context.auth.uid;
    
    // 2. Validate input
    const batch = data.batch || [];
    if (!Array.isArray(batch) || batch.length === 0) {
      throw new functions.https.HttpsError("invalid-argument", "Batch must be a non-empty array.");
    }
    
    const requiredBalance = batch.length * 0.25;

    // 3. Fetch User Balance
    const userRef = db.collection("users").doc(userId);
    const userDoc = await userRef.get();
    
    if (!userDoc.exists) {
      throw new functions.https.HttpsError("not-found", "User document not found.");
    }

    const currentBalance = userDoc.data().balance || 0;
    if (currentBalance < requiredBalance) {
      throw new functions.https.HttpsError("resource-exhausted", `Insufficient balance. You need ₹${requiredBalance.toFixed(2)} to process ${batch.length} files. Current balance: ₹${currentBalance.toFixed(2)}`);
    }

    // 4. Process with OpenAI
    const prompt = `You are an expert document classification and naming assistant.

Your task is to analyze an array of OCR text snippets extracted from multiple documents. For each document, determine:
1. The nature/type of the document.
2. The primary entity, company, or person's name.
3. The financial year, assessment year, date, or period mentioned (if any).
4. A concise and standardized file name suitable for document management systems.

Possible document types include but are not limited to:
* Balance Sheet, Profit & Loss Account, Income Tax Return, GST Return, Net Worth Certificate, No Due Certificate, Bank Statement, Audit Report, Partnership Deed, Incorporation Certificate, PAN Card, Aadhaar Card, Rent Agreement, Loan Sanction Letter, Purchase Invoice, Sale Invoice, Form 16, Form 26AS, Property Documents, ROC Filing, Other

Rules:
* Extract the most relevant person/company name that is the SUBJECT of the document.
* IMPORTANT: If the document is a letterhead, certificate, or report issued by a Chartered Accountant, Auditor, or Bank, DO NOT use the CA firm or Bank's name as the entity. Find the client or subject's name.
* Ignore OCR noise, page numbers, headers, footers, and repeated text.
* If a financial year is found, include it in the filename.
* Create a short filename using the format: <Document Type>_<Entity Name>_<Period>

Return ONLY a valid JSON ARRAY of objects in the following format:
[
  {
    "id": 0,
    "suggested_file_name": ""
  }
]

Documents to Process:
${JSON.stringify(batch)}`;

    try {
      const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
      const completion = await openai.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.3
      });
      
      const content = completion.choices[0].message.content;
      
      // Try to parse the JSON array
      let parsedContent = content.trim();
      if (parsedContent.startsWith("```json")) parsedContent = parsedContent.substring(7);
      else if (parsedContent.startsWith("```")) parsedContent = parsedContent.substring(3);
      if (parsedContent.endsWith("```")) parsedContent = parsedContent.substring(0, parsedContent.length - 3);
      
      const resultsArray = JSON.parse(parsedContent.trim());
      const resultsDict = {};
      
      // Clean the names
      for (const obj of resultsArray) {
        if (obj.suggested_file_name) {
          resultsDict[obj.id] = obj.suggested_file_name.replace(/[^a-zA-Z0-9_\-]/g, '');
        }
      }

      // 5. Deduct Balance and Log Transaction
      await userRef.update({
        balance: admin.firestore.FieldValue.increment(-requiredBalance)
      });
      
      await db.collection("transactions").add({
        uid: userId,
        type: "DEBIT",
        description: `Smart Rename Batch (${batch.length} files)`,
        amount: -requiredBalance,
        created_at: admin.firestore.FieldValue.serverTimestamp()
      });

      return {
        success: true,
        results: resultsDict,
        costCharged: requiredBalance
      };

    } catch (error) {
      console.error("Smart Rename Error:", error);
      throw new functions.https.HttpsError("internal", error.message);
    }
  });

exports.createCashfreeOrder = functions
  .runWith({ secrets: ["CASHFREE_APP_ID", "CASHFREE_SECRET_KEY"] })
  .https.onCall(async (data, context) => {
    if (!context.auth) {
      throw new functions.https.HttpsError("unauthenticated", "User must be logged in.");
    }
    
    const amount = parseFloat(data.amount);
    if (isNaN(amount) || amount <= 0) {
      throw new functions.https.HttpsError("invalid-argument", "Invalid amount.");
    }

    const orderId = `order_${context.auth.uid}_${Date.now()}`;
    const customerId = context.auth.uid;
    const customerEmail = context.auth.token.email || "no-email@shielddocs.com";
    const customerPhone = "9999999999"; 

    const expiryDate = new Date(Date.now() + 5 * 60 * 1000); // 5 minutes from now

    const payload = {
      order_id: orderId,
      order_amount: amount,
      order_currency: "INR",
      order_expiry_time: expiryDate.toISOString(),
      customer_details: {
        customer_id: customerId,
        customer_email: customerEmail,
        customer_phone: customerPhone
      }
    };

    try {
      const response = await fetch("https://api.cashfree.com/pg/orders", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "x-api-version": "2023-08-01",
          "x-client-id": process.env.CASHFREE_APP_ID,
          "x-client-secret": process.env.CASHFREE_SECRET_KEY
        },
        body: JSON.stringify(payload)
      });

      const orderData = await response.json();

      if (!response.ok) {
        console.error("Cashfree order error:", orderData);
        throw new functions.https.HttpsError("internal", `Cashfree rejected: ${JSON.stringify(orderData)}`);
      }

      await db.collection("orders").doc(orderId).set({
        uid: context.auth.uid,
        amount: amount,
        status: "PENDING",
        created_at: admin.firestore.FieldValue.serverTimestamp()
      });

      return {
        payment_session_id: orderData.payment_session_id,
        order_id: orderId
      };
    } catch (error) {
      console.error("Error creating order:", error);
      throw new functions.https.HttpsError("internal", error.message || "Failed to create order");
    }
  });

exports.verifyCashfreePayment = functions
  .runWith({ secrets: ["CASHFREE_APP_ID", "CASHFREE_SECRET_KEY"] })
  .https.onCall(async (data, context) => {
    if (!context.auth) {
      throw new functions.https.HttpsError("unauthenticated", "User must be logged in.");
    }
    
    const orderId = data.order_id;
    if (!orderId) {
      throw new functions.https.HttpsError("invalid-argument", "Order ID required.");
    }

    const orderRef = db.collection("orders").doc(orderId);
    const orderDoc = await orderRef.get();
    
    if (!orderDoc.exists) {
      throw new functions.https.HttpsError("not-found", "Order not found.");
    }
    
    if (orderDoc.data().status === "PAID") {
      return { success: true, message: "Already paid." };
    }
    
    if (orderDoc.data().uid !== context.auth.uid) {
      throw new functions.https.HttpsError("permission-denied", "Order mismatch.");
    }

    try {
      const response = await fetch(`https://api.cashfree.com/pg/orders/${orderId}`, {
        method: "GET",
        headers: {
          "Accept": "application/json",
          "x-api-version": "2023-08-01",
          "x-client-id": process.env.CASHFREE_APP_ID,
          "x-client-secret": process.env.CASHFREE_SECRET_KEY
        }
      });

      const orderData = await response.json();

      if (orderData.order_status === "PAID") {
        const amount = orderDoc.data().amount;
        
        await db.runTransaction(async (transaction) => {
          const uRef = db.collection("users").doc(context.auth.uid);
          const uDoc = await transaction.get(uRef);
          
          if (!uDoc.exists) {
             transaction.set(uRef, { balance: amount }, { merge: true });
          } else {
             transaction.update(uRef, {
                balance: admin.firestore.FieldValue.increment(amount)
             });
          }
          
          transaction.update(orderRef, { status: "PAID" });
          
          const txnRef = db.collection("transactions").doc();
          transaction.set(txnRef, {
            uid: context.auth.uid,
            type: "CREDIT",
            description: "Wallet Top Up",
            amount: amount,
            created_at: admin.firestore.FieldValue.serverTimestamp()
          });
        });
        
        return { success: true };
      } else {
        return { success: false, status: orderData.order_status };
      }
    } catch (error) {
      console.error("Verification error:", error);
      throw new functions.https.HttpsError("internal", "Verification failed.");
    }
  });


