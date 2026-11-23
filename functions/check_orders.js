const admin = require('firebase-admin');
const serviceAccount = require('./serviceAccountKey.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function checkOrders() {
  const snapshot = await db.collection('orders').get();
  console.log("Total orders:", snapshot.size);
  snapshot.forEach(doc => {
    console.log(doc.id, '=>', doc.data());
  });
  
  const userSnapshot = await db.collection('users').get();
  console.log("Total users:", userSnapshot.size);
  userSnapshot.forEach(doc => {
    console.log(doc.id, '=>', doc.data());
  });
}

checkOrders();
