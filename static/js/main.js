document.addEventListener('DOMContentLoaded', () => {
    function applyFileSectionStyles(htmlStr) {
        // Avoid red, blue, green to prevent clashing with highlights
        const bgColors = ['#f8fafc', '#fffbeb', '#faf5ff', '#ffedd5', '#f3f4f6'];
        let fileIndex = -1;
        let styledHtml = htmlStr.replace(/^--- (.*?) ---$/gm, (match, p1) => {
            fileIndex++;
            const bgColor = bgColors[fileIndex % bgColors.length];
            let prefix = fileIndex > 0 ? '</div>' : '';
            return `${prefix}<div style="background-color: ${bgColor}; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e5e7eb;"><div style="border-bottom: 2px solid #cbd5e1; margin-bottom: 10px; padding-bottom: 5px; font-weight: bold; color: #475569; font-size: 1.1em;">--- ${p1} ---</div>`;
        });
        if (fileIndex >= 0) {
            styledHtml += '</div>';
        }
        return styledHtml;
    }

    // --- Help Modal Logic ---
    const helpOverlay = document.getElementById('help-overlay');
    const btnHelpHeader = document.getElementById('btn-help-header');
    const btnCloseHelp = document.getElementById('btn-close-help');

    if (btnHelpHeader) {
        btnHelpHeader.addEventListener('click', () => {
            helpOverlay.classList.remove('hidden');
            helpOverlay.style.display = 'flex';
        });
    }

    if (btnCloseHelp) {
        btnCloseHelp.addEventListener('click', () => {
            helpOverlay.classList.add('hidden');
            helpOverlay.style.display = 'none';
        });
    }

    // --- EULA Logic ---
    const eulaOverlay = document.getElementById('eula-overlay');
    if (!localStorage.getItem('eula_accepted')) {
        eulaOverlay.classList.remove('hidden');
        eulaOverlay.style.display = 'flex';
        document.getElementById('main-app-container').classList.add('hidden');
    }

    const btnEulaAccept = document.getElementById('btn-eula-accept');
    if (btnEulaAccept) {
        document.getElementById('btn-eula-accept').addEventListener('click', () => {
        localStorage.setItem('eula_accepted', 'true');
        document.getElementById('eula-overlay').classList.add('hidden');
        document.getElementById('eula-overlay').style.display = 'none';
        document.getElementById('main-app-container').classList.remove('hidden');
        });
    }

    // Account Ledger UI Logic
    async function loadTransactions() {
        const listDiv = document.getElementById('transactions-list');
        listDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.9rem;">Loading transactions...</div>';
        
        try {
            if (!currentUser || !window.firebaseApp) return;
            const { db, collection, query, where, getDocs, orderBy } = window.firebaseApp;
            const q = query(
                collection(db, "transactions"), 
                where("uid", "==", currentUser.uid)
            );
            const snapshot = await getDocs(q);
            
            let txns = [];
            snapshot.forEach(doc => {
                const data = doc.data();
                
                // Do not show failed or just-initiated top-ups in the final ledger
                if (data.status === "PENDING" || data.status === "FAILED") return;
                if (data.type && data.type.includes("Initiated")) return;
                if (data.description && data.description.includes("Initiated")) return;
                
                txns.push({
                    id: doc.id,
                    type: data.type,
                    amount: data.amount,
                    description: data.description,
                    time: data.created_at ? data.created_at.toDate() : new Date()
                });
            });
            
            // Sort descending by time
            txns.sort((a, b) => b.time - a.time);
            
            if (txns.length === 0) {
                listDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.9rem;">No transactions found.</div>';
                return;
            }
            
            let html = '<div style="display: flex; flex-direction: column;">';
            txns.forEach(t => {
                const color = t.type === 'CREDIT' ? '#10b981' : '#ef4444';
                const sign = t.type === 'CREDIT' ? '+' : '';
                const dateStr = t.time.toLocaleDateString() + " " + t.time.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                const amountVal = t.amount || 0;
                
                html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; border-bottom: 1px solid var(--glass-border);">
                    <div style="display: flex; flex-direction: column;">
                        <span style="font-weight: 600; color: var(--text-main); font-size: 0.95rem;">${t.description || t.type}</span>
                        <span style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">${dateStr}</span>
                    </div>
                    <span style="font-weight: 700; color: ${color}; font-size: 1.1rem;">${sign}${amountVal.toFixed(2)}</span>
                </div>
                `;
            });
            html += '</div>';
            listDiv.innerHTML = html;
            
        } catch(e) {
            console.error(e);
            listDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #ef4444; font-size: 0.9rem;">Error loading transactions.</div>';
        }
    }

    document.getElementById('user-info-container').addEventListener('click', (e) => {
        e.stopPropagation();
        const dropdown = document.getElementById('user-dropdown');
        if (dropdown.classList.contains('hidden')) {
            dropdown.classList.remove('hidden');
            dropdown.style.display = 'flex';
        } else {
            dropdown.classList.add('hidden');
            dropdown.style.display = 'none';
        }
    });

    document.addEventListener('click', () => {
        const dropdown = document.getElementById('user-dropdown');
        if (dropdown && !dropdown.classList.contains('hidden')) {
            dropdown.classList.add('hidden');
            dropdown.style.display = 'none';
        }
    });

    const btnMenuAccount = document.getElementById('btn-menu-account');
    if (btnMenuAccount) {
        btnMenuAccount.addEventListener('click', () => {
            document.getElementById('page-account').classList.remove('hidden');
            document.getElementById('page-account').style.display = 'flex';
            loadTransactions();
        });
    }

    const btnMenuDictionary = document.getElementById('btn-menu-dictionary');
    if (btnMenuDictionary) {
        btnMenuDictionary.addEventListener('click', () => {
            document.getElementById('page-dictionary').classList.remove('hidden');
            document.getElementById('page-dictionary').style.display = 'flex';
            if (typeof loadDictionary === 'function') loadDictionary();
        });
    }
    
    const btnMenuLogout = document.getElementById('btn-menu-logout');
    if (btnMenuLogout) {
        btnMenuLogout.addEventListener('click', () => {
            const { auth, signOut } = window.firebaseApp;
            signOut(auth);
            
            // Also notify Python backend to release token
            fetch('/auth/logout').catch(() => {});
        });
    }

    document.getElementById('btn-close-account').addEventListener('click', () => {
        document.getElementById('page-account').classList.add('hidden');
        document.getElementById('page-account').style.display = 'none';
    });
    
    document.getElementById('btn-close-dictionary').addEventListener('click', () => {
        document.getElementById('page-dictionary').classList.add('hidden');
        document.getElementById('page-dictionary').style.display = 'none';
    });

    document.getElementById('btn-signout').addEventListener('click', () => {
        const { auth, signOut } = window.firebaseApp;
        signOut(auth);
    });

    const btnEulaDecline = document.getElementById('btn-eula-decline');
    if (btnEulaDecline) {
        btnEulaDecline.addEventListener('click', () => {
            alert("You must accept the License Agreement to use ShieldDocs. The application will now exit.");
            // Since it's a web app wrapper, we can close the window or just blank the screen
            document.body.innerHTML = "<h2 style='text-align:center; margin-top:20vh; color:#ef4444;'>Access Denied. Please restart the app to try again.</h2>";
        });
    }
    // --- Trial & Login Logic ---
    // Wait for window.firebaseApp to be ready
    const checkFirebaseReady = setInterval(() => {
        if (window.firebaseApp) {
            clearInterval(checkFirebaseReady);
            initializeFirebaseAuth();
        }
    }, 50);

    window.localTrialStatus = null;
    
    let originalFileText = "";
    let lastAnonymizedMap = {};
    let isEditingEula = false;
    
    // Auth vars
    let currentUser = null;
    let currentUserDoc = null;
    let walletUnsubscribe = null;
    let cashfreeObj = null;

    function showLoginOverlay(message = null) {
        document.getElementById('login-overlay').classList.remove('hidden');
        document.getElementById('login-overlay').style.display = 'flex';
        document.getElementById('main-app-container').classList.add('hidden');
        if (message) {
            document.getElementById('login-subtitle').textContent = message;
        }
    }

    function hideLoginOverlay() {
        document.getElementById('login-overlay').classList.add('hidden');
        document.getElementById('login-overlay').style.display = 'none';
        document.getElementById('main-app-container').classList.remove('hidden');
        document.getElementById('login-title').style.display = 'block';
        document.getElementById('login-title').textContent = "Trial Limit Reached";
        document.getElementById('login-subtitle').textContent = "You have exhausted your 50 free OCR scans. Please log in to continue using the software.";
    }

    async function initializeFirebaseAuth() {
        const { auth, onAuthStateChanged, createUserWithEmailAndPassword, signInWithEmailAndPassword, db, doc, getDoc, setDoc, onSnapshot, collection, query, where, getDocs, increment, updateDoc, GoogleAuthProvider, signInWithRedirect, getRedirectResult, signInWithCustomToken } = window.firebaseApp;

        // Custom auth token polling will be triggered on login button click


        // Initialize Cashfree
        try {
            cashfreeObj = Cashfree({
                mode: "production" // or "sandbox"
            });
        } catch(e) { console.error("Cashfree init error", e); }

        try {
            const res = await fetch('/api/trial_status');
            window.localTrialStatus = await res.json();
        } catch (e) {
            console.error("Failed to fetch local trial status", e);
        }

        onAuthStateChanged(auth, async (user) => {
            if (user) {
                currentUser = user;
                // Fetch user doc
                const userDocRef = doc(db, 'users', user.uid);
                const userDocSnap = await getDoc(userDocRef);
                
                if (userDocSnap.exists()) {
                    currentUserDoc = userDocSnap.data();
                    
                    // Auto-sync any pending payments from past sessions
                    try {
                        const q = query(collection(db, "orders"), where("uid", "==", user.uid), where("status", "==", "PENDING"));
                        const querySnapshot = await getDocs(q);
                        querySnapshot.forEach((d) => {
                            console.log("Auto-verifying pending order:", d.id);
                            verifyPayment(d.id, true);
                        });
                    } catch(e) { console.error("Auto-sync error", e); }
                    
                    document.getElementById('wallet-container').classList.remove('hidden');
                    document.getElementById('wallet-container').style.display = 'flex';
                                    // Update UI for logged in state
                const userDisplay = document.getElementById('user-email-display');
                if (userDisplay) {
                    userDisplay.textContent = user.email;
                    const wrapper = document.getElementById('user-profile-wrapper');
                    if (wrapper) wrapper.classList.remove('hidden');
                    const volBtn = document.getElementById('btn-voluntary-login');
                    if (volBtn) volBtn.style.display = 'none';
                }
                    
                    document.getElementById('user-info-container').classList.remove('hidden');
                    document.getElementById('user-info-container').style.display = 'flex';

                    if (walletUnsubscribe) walletUnsubscribe();
                    walletUnsubscribe = onSnapshot(userDocRef, (docSnap) => {
                        const data = docSnap.data();
                        if (data) {
                            const bal = data.balance || 0;
                            document.getElementById('wallet-balance').textContent = bal.toFixed(2);
                            const headerWalletBalance = document.getElementById('header-wallet-balance');
                            if (headerWalletBalance) headerWalletBalance.textContent = bal.toFixed(2);
                        }
                    });
                    // Check if trial expired and scan count > 50
                    const firstRunDate = new Date(currentUserDoc.first_run_date);
                    const now = new Date();
                    const daysElapsed = (now - firstRunDate) / (1000 * 60 * 60 * 24);
                    
                    if (daysElapsed >= 30 && currentUserDoc.scan_count >= 50) {
                        showLoginOverlay("Your free trial and 50 scan limit has been reached. Please contact support to upgrade.");
                        // Optional: hide login inputs since they are already logged in but out of credits
                        document.getElementById('login-email').style.display = 'none';
                        document.getElementById('login-password').style.display = 'none';
                        document.getElementById('btn-login-submit').style.display = 'none';
                        const toggleLink = document.getElementById('link-toggle-signup');
                        if (toggleLink) toggleLink.parentElement.style.display = 'none';
                    } else {
                        hideLoginOverlay();
                    }
                    
                    // If we are currently on the account page, load transactions now that auth is ready
                    if (window.location.pathname.includes('account')) {
                        loadTransactions();
                    }
                } else {
                    // This shouldn't happen unless document failed to create during signup
                    hideLoginOverlay();
                }
            } else {
                currentUser = null;
                currentUserDoc = null;
                
                document.getElementById('wallet-container').classList.add('hidden');
                document.getElementById('wallet-container').style.display = 'none';
                
                const userDisplay = document.getElementById('user-email-display');
                if (userDisplay) userDisplay.textContent = '';
                const wrapper = document.getElementById('user-profile-wrapper');
                if (wrapper) wrapper.classList.add('hidden');
                const volBtn = document.getElementById('btn-voluntary-login');
                if (volBtn) volBtn.style.display = 'flex';
                
                const userInfoContainer = document.getElementById('user-info-container');
                if (userInfoContainer) {
                    userInfoContainer.classList.add('hidden');
                    userInfoContainer.style.display = 'none';
                }
                if (walletUnsubscribe) {
                    walletUnsubscribe();
                    walletUnsubscribe = null;
                }
                
                showLoginOverlay();
                
                if (window.localTrialStatus && window.localTrialStatus.locked) {
                    showLoginOverlay("Your local 30-day trial and 50 scan limit has been reached. Please log in to continue.");
                } else {
                    // Not logged in but trial is still active locally
                    hideLoginOverlay();
                }
            }
        });

        // Email/Password login logic has been removed.
        
        const googleLoginBtn = document.getElementById('btn-google-login');
        const cancelLoginBtn = document.getElementById('btn-cancel-login');
        const voluntaryLoginBtn = document.getElementById('btn-voluntary-login');
        let pollInterval = null;
        let timeoutHandle = null;
        
        if (voluntaryLoginBtn) {
            voluntaryLoginBtn.addEventListener('click', () => {
                const overlay = document.getElementById('login-overlay');
                if (overlay) {
                    overlay.classList.remove('hidden');
                    overlay.style.display = 'flex';
                    const title = document.getElementById('login-title');
                    const subtitle = document.getElementById('login-subtitle');
                    if (title) title.textContent = "Login to ShieldDocs";
                    if (subtitle) subtitle.textContent = "Sign in to access advanced features and save your preferences.";
                    
                    // Show cancel button to let them close the overlay if they haven't started auth
                    if (cancelLoginBtn) cancelLoginBtn.style.display = 'block';
                }
            });
        }
        
        if (cancelLoginBtn) {
            cancelLoginBtn.addEventListener('click', () => {
                if (pollInterval) clearInterval(pollInterval);
                if (timeoutHandle) clearTimeout(timeoutHandle);
                googleLoginBtn.disabled = false;
                googleLoginBtn.textContent = 'Continue with Google';
                cancelLoginBtn.style.display = 'none';
                
                // Hide overlay if it was just a voluntary login attempt
                const overlay = document.getElementById('login-overlay');
                if (overlay && googleLoginBtn.textContent === 'Continue with Google') {
                    overlay.classList.add('hidden');
                    overlay.style.display = 'none';
                }
            });
        }
        
        if (googleLoginBtn) {
            googleLoginBtn.addEventListener('click', async () => {
                try {
                    googleLoginBtn.disabled = true;
                    googleLoginBtn.textContent = 'Please complete login in your browser...';
                    if (cancelLoginBtn) cancelLoginBtn.style.display = 'block';
                    
                    // Trigger the Python backend to open the browser
                    const res = await fetch('/auth/login');
                    if (!res.ok) throw new Error("Failed to start login flow");
                    
                    // Start polling for the custom token
                    pollInterval = setInterval(async () => {
                        try {
                            const statusRes = await fetch('/auth/status');
                            const statusData = await statusRes.json();
                            
                            if (statusData.status === 'success' && statusData.token) {
                                clearInterval(pollInterval);
                                if (timeoutHandle) clearTimeout(timeoutHandle);
                                googleLoginBtn.textContent = 'Authenticating...';
                                if (cancelLoginBtn) cancelLoginBtn.style.display = 'none';
                                
                                const userCredential = await signInWithCustomToken(auth, statusData.token);
                                
                                // Create firestore doc if new user
                                const userRef = doc(db, 'users', userCredential.user.uid);
                                const userSnap = await getDoc(userRef);
                                if (!userSnap.exists()) {
                                    await setDoc(userRef, {
                                        email: userCredential.user.email,
                                        scan_count: 0,
                                        first_run_date: new Date().toISOString()
                                    });
                                }
                                
                                googleLoginBtn.disabled = false;
                                googleLoginBtn.textContent = 'Continue with Google';
                            }
                        } catch (err) {
                            console.error("Polling error:", err);
                        }
                    }, 1000);
                    
                    // Timeout after 2 minutes
                    timeoutHandle = setTimeout(() => {
                        clearInterval(pollInterval);
                        if (googleLoginBtn.disabled) {
                            googleLoginBtn.disabled = false;
                            googleLoginBtn.textContent = 'Continue with Google';
                            if (cancelLoginBtn) cancelLoginBtn.style.display = 'none';
                            alert("Login timed out. Please try again.");
                        }
                    }, 120000);
                    
                } catch (error) {
                    alert(`Error: ${error.message}`);
                    googleLoginBtn.disabled = false;
                    googleLoginBtn.textContent = 'Continue with Google';
                    if (cancelLoginBtn) cancelLoginBtn.style.display = 'none';
                }
            });
        }
    }

    // --- Routing & Tabs Logic ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Top-level pages
    const pageMain = document.getElementById('page-main');
    const pageAccount = document.getElementById('page-account');
    const pageDictionary = document.getElementById('page-dictionary');

    function switchTab(path, pushHistory = true) {
        if (!path || path === '') path = 'redact';
        
        // Ignore modal paths if they end up here via history pop
        if (path === 'account' || path === 'dictionary') {
            path = 'redact';
        }

        pageMain.classList.remove('hidden');
        
        // Handle internal tabs inside page-main
        let foundBtn = null;
        for (let i = 0; i < tabBtns.length; i++) {
            if (tabBtns[i].dataset.path === path) {
                foundBtn = tabBtns[i];
                break;
            }
        }

        if (foundBtn) {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            foundBtn.classList.add('active');
            document.getElementById(foundBtn.dataset.target).classList.add('active');
        }

        if (pushHistory) {
            history.pushState({ path: path }, '', '/' + path);
        }
    }

    // Initialize state from URL on page load
    const initialPath = window.location.pathname.substring(1);
    switchTab(initialPath, false);

    // Handle browser Back/Forward buttons
    window.addEventListener('popstate', (e) => {
        const path = window.location.pathname.substring(1);
        switchTab(path, false);
    });

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.path, true);
        });
    });

    // --- File Upload Logic (Anonymize) ---
    setupAnonymizerFlow();

    // --- File Upload Logic (Restore) ---
    setupUploader(
        'restore', 
        '/upload_restore', 
        'Restore & Download',
        'paste-restore-input'
    );

    // --- Mapping Dictionary Logic ---
    // (Removed as per new layout)
    
    // Load saved API Key if it exists
    const savedApiKey = localStorage.getItem('openai_api_key');
    if (savedApiKey) {
        document.getElementById('openai-api-key').value = savedApiKey;
        const apiKeyContainer = document.getElementById('api-key-container');
        if(apiKeyContainer) apiKeyContainer.classList.add('hidden');
    }

    function setupAnonymizerFlow() {
        const dropZone = document.getElementById('drop-zone-anonymize');
        const fileInput = document.getElementById('file-input-anonymize');
        const fileInfo = document.getElementById('file-info-anonymize');
        const fileNameSpan = fileInfo.querySelector('.file-name');
        const removeBtn = document.getElementById('remove-btn-anonymize');
        const btnAnalyze = document.getElementById('btn-analyze');
        const btnApprove = document.getElementById('btn-approve');
        const progressContainer = document.getElementById('progress-anonymize');
        const reviewContainer = document.getElementById('review-container');
        const reviewTableBody = document.getElementById('review-table-body');
        const rawTextContainer = document.getElementById('raw-text-container');
        const rawTextarea = document.getElementById('raw-text');
        const btnAddSelected = document.getElementById('btn-add-selected');
        const searchRawInput = document.getElementById('search-raw-input');
        const btnSearchRaw = document.getElementById('btn-search-raw');
        


        let lastSearchIndex = 0;
        let lastSearchTerm = "";

        let currentFiles = [];
        let serverFilenames = [];
        let fileInfoList = [];
        let rawTextString = "";

        function getMappingsKeys() {
            const keys = [];
            document.querySelectorAll('.mapping-checkbox:checked').forEach(checkbox => {
                if (checkbox.dataset.orig) {
                    keys.push(checkbox.dataset.orig);
                } else if (checkbox.dataset.groupOrigs) {
                    try {
                        const origs = JSON.parse(checkbox.dataset.groupOrigs);
                        keys.push(...origs);
                    } catch(e) {}
                }
            });
            return keys;
        }

        function updateRawTextHighlights() {
            if (!rawTextarea) return;
            if (!rawTextString) {
                rawTextarea.innerHTML = '';
                return;
            }
            
            const keys = getMappingsKeys();
            if (keys.length === 0) {
                rawTextarea.textContent = rawTextString;
                return;
            }
            
            const safeKeys = keys.map(escapeHtml);
            safeKeys.sort((a, b) => b.length - a.length);
            const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const safePattern = new RegExp('(?<![a-zA-Z0-9])(' + safeKeys.map(escapeRegExp).join('|') + ')(?![a-zA-Z0-9])', 'gi');
            
            let html = escapeHtml(rawTextString).replace(safePattern, '<mark style="background-color: rgba(239, 68, 68, 0.5); color: #fff; padding: 0 2px; border-radius: 2px;">$1</mark>');
            rawTextarea.innerHTML = applyFileSectionStyles(html);
        }

        reviewTableBody.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('mapping-checkbox')) {
                updateRawTextHighlights();
            }
        });


        // Click to browse
        dropZone.addEventListener('click', () => fileInput.click());

        // Drag and Drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFileSelect(Array.from(e.dataTransfer.files));
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFileSelect(Array.from(fileInput.files));
            }
        });

        removeBtn.addEventListener('click', resetFlow);

        btnAnalyze.addEventListener('click', async () => {
            if (currentFiles.length === 0) return;

            // Enforce limits
            if (!currentUser) {
                if (window.localTrialStatus && window.localTrialStatus.locked) {
                    alert("Your local 30-day trial and 50 scan limit has been reached. Please log in to continue.");
                    return;
                }
            } else if (currentUserDoc) {
                const firstRunDate = new Date(currentUserDoc.first_run_date);
                const now = new Date();
                const daysElapsed = (now - firstRunDate) / (1000 * 60 * 60 * 24);
                if (daysElapsed >= 30 && currentUserDoc.scan_count >= 50) {
                    alert("Your trial limit of 50 scans has been reached. Please contact support.");
                    return;
                }
            }

            const formData = new FormData();
            currentFiles.forEach(f => formData.append('files', f));

            btnAnalyze.disabled = true;
            btnAnalyze.textContent = 'Analyzing...';
            const globalOverlay = document.getElementById('global-loading-overlay');
            globalOverlay.classList.remove('hidden');
            const progressSpan = document.getElementById('global-loading-text');
            progressSpan.style.transition = "opacity 0.3s ease";
            progressSpan.textContent = 'Analyzing document for sensitive data...';

            try {
                const response = await fetch('/analyze_file', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to analyze file');
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let mappings = {};
                let resultData = null;
                let buffer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n\n');
                    buffer = lines.pop(); // keep the last incomplete chunk in buffer
                    
                    for (let block of lines) {
                        if (block.startsWith('data: ')) {
                            const dataStr = block.replace('data: ', '').trim();
                            if (dataStr) {
                                try {
                                    const parsed = JSON.parse(dataStr);
                                    if (parsed.status === 'progress') {
                                        progressSpan.textContent = parsed.message;
                                    } else if (parsed.status === 'complete') {
                                        mappings = parsed.mappings;
                                    } else if (parsed.status === 'done') {
                                        resultData = parsed;
                                    }
                                } catch(e) {
                                    console.error("Error parsing chunk", e, dataStr);
                                }
                            }
                        }
                    }
                }
                
                if (!resultData) throw new Error("Stream closed before completion.");
                
                const data = {
                    filenames: resultData.filenames,
                    extracted_text: resultData.extracted_text,
                    mappings: resultData.mappings || mappings,
                    file_info_list: resultData.file_info_list
                };

                serverFilenames = data.filenames;
                fileInfoList = data.file_info_list || [];
                rawTextString = data.extracted_text || 'No text extracted.';
                
                // --- Increment scan count in Firestore ---
                try {
                    const { db, doc, updateDoc, increment, setDoc } = window.firebaseApp;
                    if (currentUser) {
                        const userRef = doc(db, 'users', currentUser.uid);
                        updateDoc(userRef, {
                            scan_count: increment(1)
                        }).catch(e => console.error("Firebase updateDoc failed:", e));
                        if (currentUserDoc) currentUserDoc.scan_count += 1;
                    } else if (window.localTrialStatus && window.localTrialStatus.machine_id) {
                        const deviceRef = doc(db, 'users', window.localTrialStatus.machine_id);
                        setDoc(deviceRef, {
                            scan_count: increment(1),
                            last_active: new Date().toISOString(),
                            is_anonymous: true,
                            hostname: window.localTrialStatus.hostname || 'Unknown'
                        }, { merge: true }).catch(e => console.error("Firebase setDoc failed:", e));
                    }
                } catch (dbErr) {
                    console.error("Failed to update usage count in Firebase:", dbErr);
                }

                // Populate raw text
                if (rawTextarea) {
                    rawTextString = data.extracted_text || 'No text extracted.';
                }
                
                // Populate review table
                reviewTableBody.innerHTML = '';
                const finalMappings = data.mappings;
                
                if (Object.keys(finalMappings).length === 0) {
                    reviewTableBody.innerHTML = '<tr><td colspan="3" style="text-align:center;">No sensitive data found.</td></tr>';
                } else {
                    const groupedMappings = {};
                    for (const [orig, dummy] of Object.entries(finalMappings)) {
                        if (!groupedMappings[dummy]) groupedMappings[dummy] = [];
                        groupedMappings[dummy].push(orig);
                    }
                    for (const [dummy, origs] of Object.entries(groupedMappings)) {
                        const tr = document.createElement('tr');
                        const origsJson = escapeHtml(JSON.stringify(origs));
                        const origsDisplay = origs.map(o => escapeHtml(o)).join('<br><span style="color:var(--text-muted); font-size:0.8em;">&bull;</span> ');
                        tr.innerHTML = `
                            <td><input type="checkbox" class="mapping-checkbox" data-group-origs="${origsJson}" checked></td>
                            <td>${origsDisplay}</td>
                            <td><input type="text" class="mapping-input" value="${escapeHtml(dummy)}"></td>
                        `;
                        reviewTableBody.appendChild(tr);
                    }
                }

                // Show review UI
                btnAnalyze.classList.add('hidden');
                if (rawTextContainer) rawTextContainer.classList.remove('hidden');
                reviewContainer.classList.remove('hidden');
                btnApprove.classList.remove('hidden');
                
                updateRawTextHighlights();
                
                // Auto-scroll to the results
                setTimeout(() => {
                    if (rawTextContainer) {
                        rawTextContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, 100);

            } catch (err) {
                alert('Error: ' + err.message);
                btnAnalyze.disabled = false;
                btnAnalyze.textContent = 'Analyze Document';
            } finally {
                globalOverlay.classList.add('hidden');
            }
        });

        btnApprove.addEventListener('click', async () => {
            if (serverFilenames.length === 0) return;

            // Collect edited mappings that are approved (checkbox checked)
            const customMappings = {};
            document.querySelectorAll('.mapping-checkbox:checked').forEach(checkbox => {
                if (checkbox.dataset.orig) {
                    const orig = checkbox.dataset.orig;
                    const input = document.querySelector(`.mapping-input[data-orig="${CSS.escape(orig)}"]`);
                    if (input) customMappings[orig] = input.value;
                } else if (checkbox.dataset.groupOrigs) {
                    try {
                        const origs = JSON.parse(checkbox.dataset.groupOrigs);
                        const input = checkbox.closest('tr').querySelector('.mapping-input');
                        if (input) {
                            origs.forEach(o => customMappings[o] = input.value);
                        }
                    } catch(e) {}
                }
            });

            btnApprove.disabled = true;
            btnApprove.textContent = 'Applying Redaction...';
            const globalOverlay = document.getElementById('global-loading-overlay');
            globalOverlay.classList.remove('hidden');
            const progressSpan = document.getElementById('global-loading-text');
            progressSpan.style.transition = "opacity 0.3s ease";
            progressSpan.textContent = 'Applying approved changes...';
            const messageInterval = window.startLoadingMessages(progressSpan);
            removeBtn.disabled = true;

            try {
                const response = await fetch('/apply_redaction', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filenames: serverFilenames,
                        mappings: customMappings,
                        file_info_list: fileInfoList
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to apply redaction');
                }

                const data = await response.json();

                // Show result
                document.getElementById('result-container').classList.remove('hidden');
                
                // Escape raw text content first to prevent XSS
                let highlightedText = data.text_content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                
                // Highlight dummy words in green
                Object.values(customMappings).forEach(dummy => {
                    if (!dummy) return;
                    const safeDummy = dummy.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(`\\b${safeDummy}\\b`, 'g');
                    highlightedText = highlightedText.replace(regex, `<span style="color: #10b981; font-weight: bold; background: rgba(16, 185, 129, 0.1); padding: 0 2px; border-radius: 2px;">$&</span>`);
                });
                
                // Apply file section styles with distinct background colors
                highlightedText = applyFileSectionStyles(highlightedText);
                
                document.getElementById('result-text').innerHTML = highlightedText;
                const downloadLink = document.getElementById('download-link');
                downloadLink.onclick = (e) => {
                    e.preventDefault();
                    if (window.pywebview && window.pywebview.api) {
                        const filename = data.download_url.split('/').pop();
                        window.pywebview.api.save_file(filename);
                    } else {
                        window.location.href = data.download_url;
                    }
                };
                
                // Keep the 'Analyze Document' hidden, show text, etc.
                btnApprove.classList.add('hidden');
                removeBtn.disabled = false;
                
                // Show AI Reply Hub
                // TEMPORARILY DISABLED FOR FUTURE UPDATE
                // document.getElementById('ai-reply-container').classList.remove('hidden');
                
                // Scroll to result
                setTimeout(() => {
                    document.getElementById('result-container').scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);

            } catch (err) {
                alert('Error: ' + err.message);
                btnApprove.disabled = false;
            } finally {
                clearInterval(messageInterval);
                globalOverlay.classList.add('hidden');
                btnApprove.disabled = false;
                btnApprove.textContent = 'Approve & Redact';
                removeBtn.disabled = false;
            }
        });

        if (btnAddSelected) {
            // Prevent mousedown from clearing the text selection before the click event
            btnAddSelected.addEventListener('mousedown', (e) => {
                e.preventDefault();
            });

            btnAddSelected.addEventListener('click', () => {
                const selection = window.getSelection();
                if (!selection || selection.rangeCount === 0 || !rawTextarea.contains(selection.anchorNode)) {
                    alert('Please select some text in the raw document text area first.');
                    return;
                }
                const selectedText = selection.toString().trim();
                if (!selectedText) {
                    alert('Please select some text in the raw document text area first.');
                    return;
                }
                
                // Check if it already exists in the table
                const existingInput = document.querySelector(`.mapping-input[data-orig="${CSS.escape(selectedText)}"]`);
                if (existingInput) {
                    alert('This text is already in the redaction list.');
                    return;
                }

                // Remove the 'No sensitive data found' row if it exists
                const noDataRow = reviewTableBody.querySelector('td[colspan="2"]');
                if (noDataRow) {
                    reviewTableBody.innerHTML = '';
                }
                
                // Generate a placeholder
                const randomSuffix = Math.floor(1000 + Math.random() * 9000);
                const dummyVal = `Manual_Redact_${randomSuffix}`;

                // Add new row
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="checkbox" class="mapping-checkbox" data-orig="${escapeHtml(selectedText)}" checked></td>
                    <td>${escapeHtml(selectedText)}</td>
                    <td><input type="text" class="mapping-input" data-orig="${escapeHtml(selectedText)}" value="${escapeHtml(dummyVal)}"></td>
                `;
                reviewTableBody.appendChild(tr);
                
                updateRawTextHighlights();
                window.getSelection().removeAllRanges();
            });
        }

        if (btnSearchRaw) {
            btnSearchRaw.addEventListener('click', () => {
                const term = searchRawInput.value.toLowerCase();
                if (!term) return;

                const text = rawTextString.toLowerCase();
                if (term !== lastSearchTerm) {
                    lastSearchIndex = 0;
                    lastSearchTerm = term;
                }

                const index = text.indexOf(term, lastSearchIndex);
                if (index !== -1) {
                    // Calculate redaction intervals
                    const keys = getMappingsKeys();
                    const isRedacted = new Array(rawTextString.length).fill(false);
                    if (keys.length > 0) {
                        const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                        const safeKeys = keys.sort((a, b) => b.length - a.length).map(escapeRegExp);
                        const pattern = new RegExp('(?<![a-zA-Z0-9])(' + safeKeys.join('|') + ')(?![a-zA-Z0-9])', 'gi');
                        let matchObj;
                        while ((matchObj = pattern.exec(rawTextString)) !== null) {
                            if (matchObj[0].length === 0) {
                                pattern.lastIndex++;
                                continue;
                            }
                            for (let k = 0; k < matchObj[0].length; k++) {
                                isRedacted[matchObj.index + k] = true;
                            }
                        }
                    }

                    // Search highlight interval
                    const isSearch = new Array(rawTextString.length).fill(false);
                    for (let k = 0; k < term.length; k++) {
                        isSearch[index + k] = true;
                    }

                    // Build HTML
                    let html = '';
                    let charIdx = 0;
                    while (charIdx < rawTextString.length) {
                        let r = isRedacted[charIdx];
                        let s = isSearch[charIdx];
                        let nextIdx = charIdx;
                        while (nextIdx < rawTextString.length && isRedacted[nextIdx] === r && isSearch[nextIdx] === s) {
                            nextIdx++;
                        }
                        
                        let chunk = escapeHtml(rawTextString.substring(charIdx, nextIdx));
                        if (s) {
                            let rStyle = r ? ' box-shadow: inset 0 -3px 0 0 rgba(239, 68, 68, 0.8);' : '';
                            if (charIdx === index) {
                                html += `<mark id="search-current-match" style="background-color: #3b82f6; color: #fff; padding: 0 2px; border-radius: 2px;${rStyle}">${chunk}</mark>`;
                            } else {
                                html += `<mark style="background-color: #3b82f6; color: #fff; padding: 0 2px; border-radius: 2px;${rStyle}">${chunk}</mark>`;
                            }
                        } else if (r) {
                            html += `<mark style="background-color: rgba(239, 68, 68, 0.5); color: #fff; padding: 0 2px; border-radius: 2px;">${chunk}</mark>`;
                        } else {
                            html += chunk;
                        }
                        charIdx = nextIdx;
                    }
                    rawTextarea.innerHTML = applyFileSectionStyles(html);

                    const matchElement = document.getElementById('search-current-match');
                    if (matchElement) {
                        matchElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    
                    lastSearchIndex = index + term.length;
                } else {
                    alert('No more occurrences found.');
                    lastSearchIndex = 0; // reset for next time
                    updateRawTextHighlights(); // clear search highlight
                }
            });
        }

        function handleFileSelect(files) {
            resetFlow();
            currentFiles = files;
            fileNameSpan.textContent = files.length === 1 ? files[0].name : `${files.length} files selected`;
            dropZone.style.display = 'none';
            fileInfo.classList.remove('hidden');
            btnAnalyze.disabled = false;
            btnAnalyze.classList.add('hidden'); // Hide it since it's automatic now
            
            // Auto-trigger analysis
            setTimeout(() => {
                btnAnalyze.click();
            }, 100);
        }

        function resetFlow() {
            currentFiles = [];
            serverFilenames = [];
            fileInput.value = '';
            fileInfo.classList.add('hidden');
            dropZone.style.display = 'block';
            btnAnalyze.disabled = true;
            btnAnalyze.classList.add('hidden'); // Ensure it stays hidden
            btnAnalyze.textContent = 'Analyze Document';
            if (rawTextContainer) rawTextContainer.classList.add('hidden');
            if (rawTextarea) rawTextarea.innerHTML = '';
            rawTextString = '';
            if (searchRawInput) searchRawInput.value = '';
            lastSearchIndex = 0;
            lastSearchTerm = '';
            reviewContainer.classList.add('hidden');
            btnApprove.classList.add('hidden');
            btnApprove.disabled = false;
            btnApprove.textContent = 'Approve & Redact';
            removeBtn.disabled = false;
            document.getElementById('result-container').classList.add('hidden');
            document.getElementById('result-text').textContent = '';
            
            // Reset AI Reply Hub
            document.getElementById('ai-reply-container').classList.add('hidden');
            if (localStorage.getItem('saved_ai_provider')) {
                document.getElementById('ai-provider').value = localStorage.getItem('saved_ai_provider');
            }
            document.getElementById('ai-prompt').value = '';
            document.getElementById('ai-result-section').classList.add('hidden');
            document.getElementById('ai-result-text').textContent = '';
            document.getElementById('btn-generate-reply').disabled = false;
        }

        // --- AI Reply Logic ---
        document.getElementById('btn-generate-reply').addEventListener('click', async () => {
            const provider = document.getElementById('ai-provider').value;
            const promptInstruction = document.getElementById('ai-prompt').value.trim();
            const redactedText = document.getElementById('result-text').textContent;

            if (!promptInstruction) {
                alert('Please provide a Custom Instruction (e.g., "Draft a professional email summarizing the key discrepancies in bullet points").');
                document.getElementById('ai-prompt').focus();
                return;
            }

            if (!redactedText) {
                alert('No redacted text available to send.');
                return;
            }

            localStorage.setItem('saved_ai_provider', provider);

            const btn = document.getElementById('btn-generate-reply');
            const progress = document.getElementById('progress-ai');
            const resultSection = document.getElementById('ai-result-section');
            const resultText = document.getElementById('ai-result-text');

            btn.disabled = true;
            progress.classList.remove('hidden');
            resultSection.classList.add('hidden');

            try {
                if (!window.firebaseApp || !currentUser) {
                    document.getElementById('login-title').style.display = 'none';
                    document.getElementById('login-subtitle').textContent = "You must be logged in to use AI Reply. Please log in or sign up to continue.";
                    document.getElementById('login-overlay').classList.remove('hidden');
                    document.getElementById('login-overlay').style.display = 'flex';
                    return;
                }
                const { getFunctions, httpsCallable } = window.firebaseApp;
                const functions = getFunctions();
                const generateSecureReply = httpsCallable(functions, 'generateSecureReply');
                
                // 1. Call Firebase Cloud Function
                const result = await generateSecureReply({
                    provider: provider,
                    prompt: promptInstruction || undefined,
                    redacted_text: redactedText
                });

                const cloudData = result.data;

                const redactedReply = cloudData.reply;

                // 2. Restore Text Locally
                const localResponse = await fetch('/restore_generated_text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        reply_content: redactedReply
                    })
                });

                if (!localResponse.ok) {
                    const error = await localResponse.json();
                    throw new Error(error.error || 'Failed to restore generated text locally');
                }

                const localData = await localResponse.json();
                
                resultText.textContent = localData.reply;
                resultSection.classList.remove('hidden');
                
                setTimeout(() => {
                    resultSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 100);

            } catch (err) {
                alert('Error generating AI Reply: ' + err.message);
            } finally {
                btn.disabled = false;
                progress.classList.add('hidden');
            }
        });

        const btnCopyRedacted = document.getElementById('btn-copy-redacted');
        if (btnCopyRedacted) {
            btnCopyRedacted.addEventListener('click', () => {
                const textToCopy = document.getElementById('result-text').textContent;
                if (textToCopy) {
                    navigator.clipboard.writeText(textToCopy).then(() => {
                        alert('Redacted document copied to clipboard!');
                    }).catch(err => {
                        alert('Failed to copy text: ' + err);
                    });
                } else {
                    alert('No text to copy!');
                }
            });
        }

        const btnCopyReply = document.getElementById('btn-copy-reply');
        if (btnCopyReply) {
            btnCopyReply.addEventListener('click', () => {
                const textToCopy = document.getElementById('ai-result-text').textContent;
                if (textToCopy) {
                    navigator.clipboard.writeText(textToCopy).then(() => {
                        alert('AI Reply copied to clipboard!');
                    }).catch(err => {
                        alert('Failed to copy text: ' + err);
                    });
                }
            });
        }

        const btnDownloadReplyPdf = document.getElementById('btn-download-reply-pdf');
        if (btnDownloadReplyPdf) {
            btnDownloadReplyPdf.addEventListener('click', () => {
                const element = document.getElementById('ai-result-text');
                const text = element.textContent;
                if (!text) return;
                
                if (window.jspdf && window.jspdf.jsPDF) {
                    const doc = new window.jspdf.jsPDF();
                    doc.setFont("courier");
                    doc.setFontSize(11);
                    
                    // Split text to fit within page width (180mm)
                    const splitText = doc.splitTextToSize(text, 180);
                    
                    // Print text starting at (15, 15)
                    doc.text(splitText, 15, 15);
                    doc.save('ShieldDocs_AI_Reply.pdf');
                } else {
                    alert('PDF generation library is still loading. Please try again in a moment.');
                }
            });
        }

        function getExtension(filename) {
            return filename.substring(filename.lastIndexOf('.'));
        }
    }

    function setupUploader(prefix, endpoint, defaultBtnText, textareaId = null) {
        const dropZone = document.getElementById(`drop-zone-${prefix}`);
        const fileInput = document.getElementById(`file-input-${prefix}`);
        const fileInfo = document.getElementById(`file-info-${prefix}`);
        const fileNameSpan = fileInfo.querySelector('.file-name');
        const removeBtn = fileInfo.querySelector('.remove-btn');
        const actionBtn = document.getElementById(`btn-${prefix}`);
        const progressContainer = document.getElementById(`progress-${prefix}`);
        const textarea = textareaId ? document.getElementById(textareaId) : null;

        let currentFile = null;

        let textareaTimeout = null;
        if (textarea) {
            textarea.addEventListener('input', () => {
                if (textarea.value.trim().length > 0) {
                    const blob = new Blob([textarea.value], { type: 'text/plain' });
                    currentFile = new File([blob], "pasted_reply.txt", { type: "text/plain" });
                    actionBtn.disabled = false;
                    
                    // Auto-trigger restore after 1 second of inactivity
                    clearTimeout(textareaTimeout);
                    textareaTimeout = setTimeout(() => {
                        actionBtn.click();
                    }, 1000);
                } else {
                    clearTimeout(textareaTimeout);
                    if (fileInfo.classList.contains('hidden')) {
                        currentFile = null;
                        actionBtn.disabled = true;
                    }
                }
            });
        }

        // Click to browse
        dropZone.addEventListener('click', () => fileInput.click());

        // Drag and Drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFileSelect(fileInput.files[0]);
            }
        });

        removeBtn.addEventListener('click', () => {
            currentFile = null;
            fileInput.value = '';
            fileInfo.classList.add('hidden');
            dropZone.style.display = 'block';
            if (textarea && textarea.value.trim().length > 0) {
                const blob = new Blob([textarea.value], { type: 'text/plain' });
                currentFile = new File([blob], "pasted_reply.txt", { type: "text/plain" });
                actionBtn.disabled = false;
            } else {
                actionBtn.disabled = true;
            }
        });

        actionBtn.addEventListener('click', async () => {
            if (!currentFile) return;

            const formData = new FormData();
            formData.append('file', currentFile);

            // UI State processing
            actionBtn.disabled = true;
            actionBtn.textContent = 'Processing...';
            const globalOverlay = document.getElementById('global-loading-overlay');
            globalOverlay.classList.remove('hidden');
            const progressSpan = document.getElementById('global-loading-text');
            progressSpan.style.transition = "opacity 0.3s ease";
            progressSpan.textContent = 'Processing file...';
            const messageInterval = window.startLoadingMessages(progressSpan);

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to process file');
                }

                const result = await response.json();
                
                // Fetch the actual file using the URL provided by the backend to get the text for preview
                const fileRes = await fetch(result.download_url);
                const blob = await fileRes.blob();
                
                // Set up the manual download button to use the native Save Dialog if available
                const btnDownloadRestored = document.getElementById('btn-download-restored');
                if (btnDownloadRestored) {
                    btnDownloadRestored.onclick = (e) => {
                        e.preventDefault();
                        if (window.pywebview && window.pywebview.api) {
                            window.pywebview.api.save_file(result.filename);
                        } else {
                            // Fallback for non-pywebview environments
                            btnDownloadRestored.href = result.download_url;
                            btnDownloadRestored.download = result.filename;
                            window.location.href = result.download_url;
                        }
                    };
                }

                // UI refresh for preview if it is a text file
                const restoreResultSection = document.getElementById('restore-result-section');
                const restoreResultText = document.getElementById('restore-result-text');
                
                if (restoreResultSection && restoreResultText) {
                    if (result.filename.toLowerCase().endsWith('.txt')) {
                        const text = await blob.text();
                        restoreResultText.textContent = text;
                        restoreResultSection.classList.remove('hidden');
                    } else {
                        restoreResultText.textContent = "Preview is not available for .docx files. Please open the downloaded file to view the restored content.";
                        restoreResultSection.classList.remove('hidden');
                    }
                    
                    // Smoothly scroll the user down to the restored results
                    setTimeout(() => {
                        restoreResultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 100);
                }
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                // Restore UI state
                clearInterval(messageInterval);
                actionBtn.disabled = false;
                actionBtn.textContent = defaultBtnText;
                globalOverlay.classList.add('hidden');
            }
        });

        function handleFileSelect(file) {
            currentFile = file;
            fileNameSpan.textContent = file.name;
            dropZone.style.display = 'none';
            fileInfo.classList.remove('hidden');
            actionBtn.disabled = false;
            if (textarea) textarea.value = ''; // clear text if file uploaded
            
            // Auto-trigger restore
            setTimeout(() => {
                actionBtn.click();
            }, 100);
        }

        function getExtension(filename) {
            return filename.substring(filename.lastIndexOf('.'));
        }
    }

    function renderMapping(data) {
        // UI element removed
    }

    function escapeHtml(unsafe) {
        return (unsafe || '').replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    const loadingMessages = [
        "Still working! Large documents can take a little extra time to process securely...",
        "Scanning every line... Your data privacy is our top priority.",
        "Almost there! We're making sure no sensitive information is left behind.",
        "Applying advanced pattern recognition to protect your document...",
        "Thank you for your patience. Processing is happening 100% locally on your device!",
        "Running OCR (Optical Character Recognition) on images and scanned pages...",
        "Extracting structured text formats...",
        "Mapping sensitive entities across the document...",
        "Deep scanning for Personally Identifiable Information (PII)...",
        "Cross-referencing data to ensure complete redaction...",
        "Generating secure reversible hashes for your data...",
        "Complex documents with many pages can take up to 10 minutes. Please hold on...",
        "Optimizing extracted data for review...",
        "Your file never leaves your computer during this entire process.",
        "Wrapping up the final stages of document analysis..."
    ];

    window.startLoadingMessages = function(progressSpan) {
        let msgIndex = 0;
        return setInterval(() => {
            progressSpan.style.opacity = 0;
            setTimeout(() => {
                if (msgIndex === 3) {
                    progressSpan.textContent = "If your document is an image scan, it will naturally take longer than a normal PDF.";
                } else if (msgIndex === 9) {
                    progressSpan.textContent = "Still processing... Note that for photo PDFs, some characters may be misread. We will provide both text and PDF outputs. If some words are misread, don't worry—when you submit it to the AI, it will still draw the correct meaning!";
                } else {
                    progressSpan.textContent = loadingMessages[msgIndex % loadingMessages.length];
                }
                progressSpan.style.opacity = 1;
                msgIndex++;
            }, 300);
        }, 30000);
    };

    // --- Cashfree Top Up Flow ---
    const topupOverlay = document.getElementById('topup-overlay');
    
    document.getElementById('btn-open-topup').addEventListener('click', () => {
        topupOverlay.classList.remove('hidden');
        topupOverlay.style.display = 'flex';
    });
    

    
    document.getElementById('btn-cancel-topup').addEventListener('click', () => {
        topupOverlay.classList.add('hidden');
        topupOverlay.style.display = 'none';
    });

    let selectedAmount = 0;
    
    document.querySelectorAll('.amount-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            selectedAmount = parseInt(e.target.dataset.amount);
            document.getElementById('custom-amount-input').value = selectedAmount;
        });
    });

    document.getElementById('btn-pay-now').addEventListener('click', async () => {
        const inputAmount = parseInt(document.getElementById('custom-amount-input').value);
        if (!inputAmount || inputAmount < 50) {
            alert('Minimum top-up amount is ₹50.');
            return;
        }
        
        const btnPay = document.getElementById('btn-pay-now');
        btnPay.textContent = "Processing...";
        btnPay.disabled = true;

        try {
            // 1. Create Order via Firebase Cloud Function
            const { getFunctions, httpsCallable } = window.firebaseApp;
            const functions = getFunctions();
            const createCashfreeOrder = httpsCallable(functions, 'createCashfreeOrder');
            
            const resultObj = await createCashfreeOrder({ amount: inputAmount });
            
            const paymentSessionId = resultObj.data.payment_session_id;
            const orderId = resultObj.data.order_id;
            
            // 2. Open Cashfree Checkout on Firebase Hosting
            topupOverlay.classList.add('hidden');
            topupOverlay.style.display = 'none';
            btnPay.textContent = "Proceed to Pay";
            btnPay.disabled = false;
            
            const paymentUrl = "https://shielddocs-1f6cd.web.app/payment.html?session_id=" + paymentSessionId;
            window.open(paymentUrl, "_blank");
            
            if (confirm("We have securely opened Cashfree Payments in a new tab.\n\nPlease complete your top-up there. Once you are finished, click OK here to verify your balance!")) {
                verifyPayment(orderId);
            }
            
        } catch(e) {
            console.error(e);
            alert("Error initiating payment: " + e.message);
            btnPay.textContent = "Proceed to Pay";
            btnPay.disabled = false;
        }
    });
    
    async function verifyPayment(orderId, isAutoSync = false) {
        console.log("Verifying your payment securely...");
        try {
            const { getFunctions, httpsCallable } = window.firebaseApp;
            const functions = getFunctions();
            const verifyCashfreePayment = httpsCallable(functions, 'verifyCashfreePayment');

            const vRes = await verifyCashfreePayment({ order_id: orderId });
            
            if (vRes.data.success) {
                alert("Payment Successful! Your wallet has been updated.");
            } else {
                if (!isAutoSync) {
                    if (vRes.data.status === "ACTIVE") {
                         alert("We haven't received a successful payment for this order yet.\n\nIf you cancelled the payment, you can safely close this box. If you did pay, it may take a minute to process.");
                    } else {
                         alert("Payment verification failed. Status: " + vRes.data.status);
                    }
                }
            }
        } catch(e) {
            console.error(e);
            if (!isAutoSync) {
                alert("Error verifying payment. If amount was deducted, it will reflect shortly.");
            }
        } finally {
            console.log("Verification finished.");
        }
    }
    
    // --- Dictionary Settings Logic ---
    const btnCloseDict = document.getElementById('btn-close-dictionary');
    const btnSaveDict = document.getElementById('btn-save-dictionary');
    const customWordsList = document.getElementById('custom-words-list');
    const customRegexList = document.getElementById('custom-regex-list');
    
    let currentRules = { words: [], regexes: [] };
    
    if (btnCloseDict) {
        btnCloseDict.addEventListener('click', () => {
            document.getElementById('page-dictionary').classList.add('hidden');
            document.getElementById('page-dictionary').style.display = 'none';
        });
    }
    
    async function loadDictionary() {
        try {
            const res = await fetch('/api/custom_rules');
            if (res.ok) {
                currentRules = await res.json();
                renderDictionary();
            }
        } catch (e) {
            console.error("Error loading dictionary:", e);
        }
    }
    
    function renderDictionary() {
        // Render Words
        customWordsList.innerHTML = '';
        currentRules.words.forEach((word, index) => {
            const el = document.createElement('div');
            el.style.cssText = "background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); color: #10b981; padding: 4px 10px; border-radius: 15px; display: flex; align-items: center; gap: 8px; font-size: 0.85rem;";
            el.innerHTML = `
                <span>${escapeHtml(word)}</span>
                <button data-index="${index}" class="btn-remove-word" style="background: transparent; border: none; color: #ef4444; cursor: pointer; font-size: 1rem; line-height: 1;">&times;</button>
            `;
            customWordsList.appendChild(el);
        });
        
        document.querySelectorAll('.btn-remove-word').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = e.currentTarget.getAttribute('data-index');
                currentRules.words.splice(idx, 1);
                renderDictionary();
            });
        });
        
        // Render Regexes
        customRegexList.innerHTML = '';
        currentRules.regexes.forEach((rx, index) => {
            const el = document.createElement('div');
            el.style.cssText = "background: var(--input-bg); border: 1px solid var(--input-border); padding: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;";
            el.innerHTML = `
                <div>
                    <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">${escapeHtml(rx.name)}</div>
                    <div style="color: var(--text-muted); font-size: 0.8rem; font-family: monospace;">${escapeHtml(rx.pattern)}</div>
                </div>
                <button data-index="${index}" class="btn-remove-regex" style="background: transparent; border: none; color: #ef4444; cursor: pointer; font-size: 1.2rem;">&times;</button>
            `;
            customRegexList.appendChild(el);
        });
        
        document.querySelectorAll('.btn-remove-regex').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = e.currentTarget.getAttribute('data-index');
                currentRules.regexes.splice(idx, 1);
                renderDictionary();
            });
        });
    }
    
    document.getElementById('btn-add-word').addEventListener('click', () => {
        const input = document.getElementById('custom-word-input');
        const val = input.value.trim();
        if (val && !currentRules.words.includes(val)) {
            currentRules.words.push(val);
            input.value = '';
            renderDictionary();
        }
    });
    
    document.getElementById('btn-add-regex').addEventListener('click', () => {
        const nameInput = document.getElementById('regex-name-input');
        const patternInput = document.getElementById('regex-pattern-input');
        const nameVal = nameInput.value.trim();
        const patternVal = patternInput.value.trim();
        
        if (nameVal && patternVal) {
            try {
                new RegExp(patternVal); // Test if valid regex
                currentRules.regexes.push({ name: nameVal, pattern: patternVal });
                nameInput.value = '';
                patternInput.value = '';
                renderDictionary();
            } catch (e) {
                alert("Invalid Regular Expression.");
            }
        }
    });
    
    document.getElementById('btn-save-dictionary').addEventListener('click', async () => {
        btnSaveDict.textContent = "Saving...";
        try {
            const res = await fetch('/api/custom_rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentRules)
            });
            if (res.ok) {
                alert("Dictionary saved and NLP Engine reloaded successfully!");
                switchTab('redact', true);
            } else {
                const data = await res.json();
                alert("Error saving: " + data.error);
            }
        } catch (e) {
            console.error(e);
            alert("Network error.");
        } finally {
            btnSaveDict.textContent = "Save & Apply Rules";
        }
    });
    
    // --- Smart Rename Logic ---
    let selectedFolderPath = null;
    let smartRenameResults = [];
    
    document.getElementById('btn-select-folder').addEventListener('click', async () => {
        try {
            const res = await fetch('/api/select_folder');
            const data = await res.json();
            if (data.success) {
                selectedFolderPath = data.path;
                document.getElementById('btn-select-folder').textContent = "Selected: " + selectedFolderPath;
                document.getElementById('btn-scan-folder').disabled = false;
                document.getElementById('rename-results-section').classList.add('hidden');
            }
        } catch (e) {
            console.error("Error selecting folder:", e);
        }
    });
    
    document.getElementById('btn-scan-folder').addEventListener('click', async () => {
        if (!selectedFolderPath) return;
        
        const aiProvider = null;
        const apiKey = null;
        
        const btnScan = document.getElementById('btn-scan-folder');
        btnScan.disabled = true;
        btnScan.textContent = "Scanning...";
        
        const progressContainer = document.getElementById('progress-smart-rename');
        const progressText = document.getElementById('rename-progress-text');
        progressContainer.classList.remove('hidden');
        
        document.getElementById('rename-results-section').classList.add('hidden');
        
        try {
            let idToken = null;
            if (window.firebaseApp && window.firebaseApp.auth && window.firebaseApp.auth.currentUser) {
                idToken = await window.firebaseApp.auth.currentUser.getIdToken();
            }

            const response = await fetch('/api/scan_rename_folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder_path: selectedFolderPath, ai_provider: aiProvider, api_key: apiKey, id_token: idToken })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to scan folder');
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // keep last incomplete chunk
                
                for (let block of lines) {
                    if (block.startsWith('data: ')) {
                        const dataStr = block.replace('data: ', '').trim();
                        if (dataStr) {
                            try {
                                const parsed = JSON.parse(dataStr);
                                if (parsed.status === 'progress') {
                                    progressText.textContent = parsed.message;
                                } else if (parsed.status === 'done') {
                                    smartRenameResults = parsed.results;
                                }
                            } catch (e) { console.error("Parse error", e, dataStr); }
                        }
                    }
                }
            }
            
            // Render results
            const tbody = document.getElementById('rename-table-body');
            tbody.innerHTML = '';
            
            if (smartRenameResults.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:15px;">No compatible files found.</td></tr>';
            } else {
                smartRenameResults.forEach((res, i) => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid var(--glass-border)';
                    
                    tr.innerHTML = `
                        <td style="padding: 12px; word-break: break-all;">${escapeHtml(res.original_name)}</td>
                        <td style="padding: 12px; word-break: break-all;">${res.ai_name ? escapeHtml(res.ai_name) : '-'}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            
            document.getElementById('rename-results-section').classList.remove('hidden');
            
        } catch (e) {
            alert("Error: " + e.message);
        } finally {
            progressContainer.classList.add('hidden');
            btnScan.disabled = false;
            btnScan.textContent = "Scan Files";
        }
    });
    
    document.getElementById('btn-apply-rename').addEventListener('click', async () => {
        const renames = [];
        smartRenameResults.forEach(originalData => {
            const newName = originalData.ai_name;
            if (newName && newName !== "-" && newName !== originalData.original_name) {
                renames.push({
                    original_path: originalData.original_path,
                    new_name: newName
                });
            }
        });
        
        if (renames.length === 0) {
            alert("No files selected for renaming.");
            return;
        }
        
        const btnApply = document.getElementById('btn-apply-rename');
        btnApply.disabled = true;
        btnApply.textContent = "Applying...";
        
        try {
            const res = await fetch('/api/apply_rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ renames: renames })
            });
            const data = await res.json();
            
            if (data.success) {
                alert(`Successfully renamed ${data.renamed_count} files.\nErrors: ${data.errors.length}`);
                
                // --- Increment rename_count in Firestore ---
                try {
                    const { db, doc, updateDoc, increment, setDoc } = window.firebaseApp;
                    if (currentUser) {
                        const userRef = doc(db, 'users', currentUser.uid);
                        updateDoc(userRef, {
                            rename_count: increment(1)
                        }).catch(e => console.error("Firebase updateDoc failed:", e));
                    } else if (window.localTrialStatus && window.localTrialStatus.machine_id) {
                        const deviceRef = doc(db, 'users', window.localTrialStatus.machine_id);
                        setDoc(deviceRef, {
                            rename_count: increment(1),
                            last_active: new Date().toISOString(),
                            is_anonymous: true,
                            hostname: window.localTrialStatus.hostname || 'Unknown'
                        }, { merge: true }).catch(e => console.error("Firebase setDoc failed:", e));
                    }
                } catch (dbErr) {
                    console.error("Failed to update rename count in Firebase:", dbErr);
                }

                // Hide results and reset
                document.getElementById('rename-results-section').classList.add('hidden');
                smartRenameResults = [];
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) {
            alert("Error applying renames: " + e.message);
        } finally {
            btnApply.disabled = false;
            btnApply.textContent = "Apply Selected Renames";
        }
    });

    // --- Extract Data Logic ---
    let extractFiles = [];
    const dropZoneExtract = document.getElementById('drop-zone-extract');
    const fileInputExtract = document.getElementById('file-input-extract');
    const btnExtract = document.getElementById('btn-extract');
    const fileInfoExtract = document.getElementById('file-info-extract');
    const progressExtract = document.getElementById('progress-extract');
    const extractResultsSection = document.getElementById('extract-results-section');
    const extractTableBody = document.getElementById('extract-table-body');
    const extractProgressText = document.getElementById('extract-progress-text');

    if (dropZoneExtract) {
        dropZoneExtract.addEventListener('click', () => fileInputExtract.click());
        dropZoneExtract.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZoneExtract.classList.add('drag-over');
        });
        dropZoneExtract.addEventListener('dragleave', () => dropZoneExtract.classList.remove('drag-over'));
        dropZoneExtract.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZoneExtract.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                handleExtractFiles(Array.from(e.dataTransfer.files));
            }
        });
        
        fileInputExtract.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleExtractFiles(Array.from(e.target.files));
            }
        });
    }

    function handleExtractFiles(files) {
        extractFiles = files;
        if (extractFiles.length > 0) {
            dropZoneExtract.classList.add('hidden');
            fileInfoExtract.classList.remove('hidden');
            fileInfoExtract.querySelector('.file-name').textContent = extractFiles.map(f => f.name).join(', ');
            btnExtract.classList.add('hidden'); // Hide since it auto-starts
            btnExtract.disabled = false;
            
            // Auto-trigger extraction
            setTimeout(() => {
                btnExtract.click();
            }, 100);
        }
    }

    const removeBtnExtract = document.getElementById('remove-btn-extract');
    if (removeBtnExtract) {
        removeBtnExtract.addEventListener('click', () => {
            extractFiles = [];
            fileInputExtract.value = '';
            dropZoneExtract.classList.remove('hidden');
            fileInfoExtract.classList.add('hidden');
            btnExtract.classList.add('hidden');
            extractResultsSection.classList.add('hidden');
        });
    }

    if (btnExtract) {
        btnExtract.addEventListener('click', async () => {
            if (extractFiles.length === 0) return;
            
            btnExtract.disabled = true;
            progressExtract.classList.remove('hidden');
            extractResultsSection.classList.add('hidden');
            extractProgressText.textContent = "Extracting data...";
            
            const formData = new FormData();
            extractFiles.forEach(f => formData.append('files', f));
            
            const docTypeSelect = document.getElementById('extract-doc-type');
            if (docTypeSelect) {
                formData.append('doc_type', docTypeSelect.value);
            }
            
            try {
                const response = await fetch('/extract_info', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to extract data');
                }
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";
                let finalData = [];
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n\n');
                    buffer = lines.pop(); 
                    
                    for (let block of lines) {
                        if (block.startsWith('data: ')) {
                            const dataStr = block.replace('data: ', '').trim();
                            if (dataStr) {
                                try {
                                    const parsed = JSON.parse(dataStr);
                                    if (parsed.status === 'progress') {
                                        extractProgressText.textContent = parsed.message;
                                    } else if (parsed.status === 'done') {
                                        finalData = parsed.extracted_data;
                                    }
                                } catch (e) { console.error("Parse error", e, dataStr); }
                            }
                        }
                    }
                }
                
                extractTableBody.innerHTML = '';
                if (!finalData || finalData.length === 0) {
                    extractTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:15px;">No entities found.</td></tr>';
                } else {
                    finalData.forEach(item => {
                        const tr = document.createElement('tr');
                        tr.style.borderBottom = '1px solid var(--glass-border)';
                        tr.innerHTML = `
                            <td style="padding: 12px;">${escapeHtml(item.file)}</td>
                            <td style="padding: 12px;"><span class="badge badge-system">${escapeHtml(item.type)}</span></td>
                            <td style="padding: 12px; font-weight: 600; color: #10b981; font-family: monospace; font-size: 1.1rem;">${escapeHtml(item.cleaned)}</td>
                        `;
                        extractTableBody.appendChild(tr);
                    });
                }
                extractResultsSection.classList.remove('hidden');
                
                // --- Increment extract counts in Firestore ---
                try {
                    const { db, doc, updateDoc, increment, setDoc } = window.firebaseApp;
                    let incrementField = null;
                    if (docTypeSelect) {
                        if (docTypeSelect.value === 'pan') incrementField = 'pan_extract_count';
                        else if (docTypeSelect.value === 'aadhaar') incrementField = 'aadhaar_extract_count';
                    }
                    if (incrementField) {
                        if (currentUser) {
                            const userRef = doc(db, 'users', currentUser.uid);
                            updateDoc(userRef, {
                                [incrementField]: increment(1)
                            }).catch(e => console.error("Firebase updateDoc failed:", e));
                        } else if (window.localTrialStatus && window.localTrialStatus.machine_id) {
                            const deviceRef = doc(db, 'users', window.localTrialStatus.machine_id);
                            setDoc(deviceRef, {
                                [incrementField]: increment(1),
                                last_active: new Date().toISOString(),
                                is_anonymous: true,
                                hostname: window.localTrialStatus.hostname || 'Unknown'
                            }, { merge: true }).catch(e => console.error("Firebase setDoc failed:", e));
                        }
                    }
                } catch (dbErr) {
                    console.error("Failed to update extract count in Firebase:", dbErr);
                }
                
            } catch (e) {
                alert("Error: " + e.message);
            } finally {
                progressExtract.classList.add('hidden');
                btnExtract.disabled = false;
            }
        });
    }

    // --- Merge PDF Logic ---
    let mergeFiles = [];
    const dropZoneMerge = document.getElementById('drop-zone-merge');
    const fileInputMerge = document.getElementById('file-input-merge');
    const btnMerge = document.getElementById('btn-merge');
    const progressMerge = document.getElementById('progress-merge');
    const mergeFileList = document.getElementById('merge-file-list');

    if (dropZoneMerge) {
        dropZoneMerge.addEventListener('click', () => fileInputMerge.click());
        dropZoneMerge.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZoneMerge.classList.add('drag-over');
        });
        dropZoneMerge.addEventListener('dragleave', () => dropZoneMerge.classList.remove('drag-over'));
        dropZoneMerge.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZoneMerge.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                handleMergeFiles(Array.from(e.dataTransfer.files));
            }
        });
        
        fileInputMerge.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleMergeFiles(Array.from(e.target.files));
            }
        });
    }

    function renderMergeFiles() {
        mergeFileList.innerHTML = '';
        if (mergeFiles.length > 0) {
            btnMerge.classList.remove('hidden');
            btnMerge.disabled = false;
        } else {
            btnMerge.classList.add('hidden');
            btnMerge.disabled = true;
        }
        
        mergeFiles.forEach((file, index) => {
            const div = document.createElement('div');
            div.style.display = 'flex';
            div.style.justifyContent = 'space-between';
            div.style.alignItems = 'center';
            div.style.padding = '10px';
            div.style.background = 'var(--glass-bg)';
            div.style.border = '1px solid var(--glass-border)';
            div.style.borderRadius = '6px';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = `${index + 1}. ${file.name}`;
            nameSpan.style.flex = '1';
            nameSpan.style.overflow = 'hidden';
            nameSpan.style.textOverflow = 'ellipsis';
            nameSpan.style.whiteSpace = 'nowrap';
            
            const controls = document.createElement('div');
            controls.style.display = 'flex';
            controls.style.gap = '5px';
            
            const btnUp = document.createElement('button');
            btnUp.innerHTML = '↑';
            btnUp.className = 'action-btn';
            btnUp.style.margin = '0';
            btnUp.style.padding = '4px 8px';
            btnUp.style.minHeight = '0';
            btnUp.disabled = index === 0;
            btnUp.onclick = () => {
                const temp = mergeFiles[index - 1];
                mergeFiles[index - 1] = mergeFiles[index];
                mergeFiles[index] = temp;
                renderMergeFiles();
            };
            
            const btnDown = document.createElement('button');
            btnDown.innerHTML = '↓';
            btnDown.className = 'action-btn';
            btnDown.style.margin = '0';
            btnDown.style.padding = '4px 8px';
            btnDown.style.minHeight = '0';
            btnDown.disabled = index === mergeFiles.length - 1;
            btnDown.onclick = () => {
                const temp = mergeFiles[index + 1];
                mergeFiles[index + 1] = mergeFiles[index];
                mergeFiles[index] = temp;
                renderMergeFiles();
            };
            
            const btnRemove = document.createElement('button');
            btnRemove.innerHTML = '✕';
            btnRemove.className = 'remove-btn';
            btnRemove.style.position = 'static';
            btnRemove.onclick = () => {
                mergeFiles.splice(index, 1);
                renderMergeFiles();
            };
            
            controls.appendChild(btnUp);
            controls.appendChild(btnDown);
            controls.appendChild(btnRemove);
            
            div.appendChild(nameSpan);
            div.appendChild(controls);
            mergeFileList.appendChild(div);
        });
    }

    function handleMergeFiles(files) {
        files.forEach(f => {
            if (f.name.toLowerCase().endsWith('.pdf')) {
                mergeFiles.push(f);
            }
        });
        renderMergeFiles();
    }

    if (btnMerge) {
        btnMerge.addEventListener('click', async () => {
            if (mergeFiles.length === 0) return;
            
            btnMerge.disabled = true;
            progressMerge.classList.remove('hidden');
            
            const formData = new FormData();
            mergeFiles.forEach(f => formData.append('files', f));
            
            try {
                const response = await fetch('/api/merge_pdf', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to merge PDFs');
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                // Get filename from header if possible, else default
                let filename = "Merged_Document.pdf";
                const disposition = response.headers.get('Content-Disposition');
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) { 
                        filename = matches[1].replace(/['"]/g, '');
                    }
                }
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                
                // --- Increment merge_count in Firestore ---
                try {
                    const { db, doc, updateDoc, increment, setDoc } = window.firebaseApp;
                    if (currentUser) {
                        const userRef = doc(db, 'users', currentUser.uid);
                        updateDoc(userRef, {
                            merge_count: increment(1)
                        }).catch(e => console.error("Firebase updateDoc failed:", e));
                    } else if (window.localTrialStatus && window.localTrialStatus.machine_id) {
                        const deviceRef = doc(db, 'users', window.localTrialStatus.machine_id);
                        setDoc(deviceRef, {
                            merge_count: increment(1),
                            last_active: new Date().toISOString(),
                            is_anonymous: true,
                            hostname: window.localTrialStatus.hostname || 'Unknown'
                        }, { merge: true }).catch(e => console.error("Firebase setDoc failed:", e));
                    }
                } catch (dbErr) {
                    console.error("Failed to update merge count in Firebase:", dbErr);
                }
                
            } catch (e) {
                alert("Error: " + e.message);
            } finally {
                progressMerge.classList.add('hidden');
                btnMerge.disabled = false;
            }
        });
    }

    // --- Split PDF Logic ---
    let splitFile = null;
    const dropZoneSplit = document.getElementById('drop-zone-split');
    const fileInputSplit = document.getElementById('file-input-split');
    const btnSplit = document.getElementById('btn-split');
    const progressSplit = document.getElementById('progress-split');
    const splitOptions = document.getElementById('split-options');
    const fileInfoSplit = document.getElementById('file-info-split');
    const removeBtnSplit = document.getElementById('remove-btn-split');

    if (dropZoneSplit) {
        dropZoneSplit.addEventListener('click', () => fileInputSplit.click());
        dropZoneSplit.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZoneSplit.classList.add('drag-over');
        });
        dropZoneSplit.addEventListener('dragleave', () => dropZoneSplit.classList.remove('drag-over'));
        dropZoneSplit.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZoneSplit.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                handleSplitFile(e.dataTransfer.files[0]);
            }
        });
        
        fileInputSplit.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleSplitFile(e.target.files[0]);
            }
        });
    }

    function handleSplitFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert("Only PDF files are supported.");
            return;
        }
        splitFile = file;
        dropZoneSplit.classList.add('hidden');
        fileInfoSplit.classList.remove('hidden');
        fileInfoSplit.querySelector('.file-name').textContent = file.name;
        
        splitOptions.classList.remove('hidden');
        btnSplit.classList.remove('hidden');
        btnSplit.disabled = false;
    }
    
    if (removeBtnSplit) {
        removeBtnSplit.addEventListener('click', () => {
            splitFile = null;
            fileInputSplit.value = '';
            dropZoneSplit.classList.remove('hidden');
            fileInfoSplit.classList.add('hidden');
            splitOptions.classList.add('hidden');
            btnSplit.classList.add('hidden');
        });
    }

    if (btnSplit) {
        btnSplit.addEventListener('click', async () => {
            if (!splitFile) return;
            const sequenceInput = document.getElementById('split-sequence');
            if (!sequenceInput || !sequenceInput.value.trim()) {
                alert("Please provide a page sequence.");
                return;
            }
            
            btnSplit.disabled = true;
            progressSplit.classList.remove('hidden');
            
            const formData = new FormData();
            formData.append('file', splitFile);
            formData.append('sequence', sequenceInput.value.trim());
            
            try {
                const response = await fetch('/api/split_pdf', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to process PDF');
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                let filename = "Split_Document.pdf";
                const disposition = response.headers.get('Content-Disposition');
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) { 
                        filename = matches[1].replace(/['"]/g, '');
                    }
                }
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                
                // --- Increment split_count in Firestore ---
                try {
                    const { db, doc, updateDoc, increment, setDoc } = window.firebaseApp;
                    if (currentUser) {
                        const userRef = doc(db, 'users', currentUser.uid);
                        updateDoc(userRef, {
                            split_count: increment(1)
                        }).catch(e => console.error("Firebase updateDoc failed:", e));
                    } else if (window.localTrialStatus && window.localTrialStatus.machine_id) {
                        const deviceRef = doc(db, 'users', window.localTrialStatus.machine_id);
                        setDoc(deviceRef, {
                            split_count: increment(1),
                            last_active: new Date().toISOString(),
                            is_anonymous: true,
                            hostname: window.localTrialStatus.hostname || 'Unknown'
                        }, { merge: true }).catch(e => console.error("Firebase setDoc failed:", e));
                    }
                } catch (dbErr) {
                    console.error("Failed to update split count in Firebase:", dbErr);
                }
                
            } catch (e) {
                alert("Error: " + e.message);
            } finally {
                progressSplit.classList.add('hidden');
                btnSplit.disabled = false;
            }
        });
    }

    // --- Compress PDF Logic ---
    let compressFile = null;
    const dropZoneCompress = document.getElementById('drop-zone-compress');
    const fileInputCompress = document.getElementById('file-input-compress');
    const btnCompress = document.getElementById('btn-compress');
    const progressCompress = document.getElementById('progress-compress');
    const fileInfoCompress = document.getElementById('file-info-compress');
    const removeBtnCompress = document.getElementById('remove-btn-compress');

    if (dropZoneCompress) {
        dropZoneCompress.addEventListener('click', () => fileInputCompress.click());
        dropZoneCompress.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZoneCompress.classList.add('drag-over');
        });
        dropZoneCompress.addEventListener('dragleave', () => dropZoneCompress.classList.remove('drag-over'));
        dropZoneCompress.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZoneCompress.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                handleCompressFile(e.dataTransfer.files[0]);
            }
        });
        
        fileInputCompress.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleCompressFile(e.target.files[0]);
            }
        });
    }

    function handleCompressFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert("Only PDF files are supported.");
            return;
        }
        compressFile = file;
        dropZoneCompress.classList.add('hidden');
        fileInfoCompress.classList.remove('hidden');
        fileInfoCompress.querySelector('.file-name').textContent = file.name;
        
        btnCompress.classList.remove('hidden');
        btnCompress.disabled = false;
    }
    
    if (removeBtnCompress) {
        removeBtnCompress.addEventListener('click', () => {
            compressFile = null;
            fileInputCompress.value = '';
            dropZoneCompress.classList.remove('hidden');
            fileInfoCompress.classList.add('hidden');
            btnCompress.classList.add('hidden');
        });
    }

    if (btnCompress) {
        btnCompress.addEventListener('click', async () => {
            if (!compressFile) return;
            
            btnCompress.disabled = true;
            progressCompress.classList.remove('hidden');
            
            const formData = new FormData();
            formData.append('file', compressFile);
            
            try {
                const response = await fetch('/api/compress_pdf', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to compress PDF');
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                let filename = "Compressed_Document.pdf";
                const disposition = response.headers.get('Content-Disposition');
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) { 
                        filename = matches[1].replace(/['"]/g, '');
                    }
                }
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                
                // --- Increment compress_count in Firestore ---
                try {
                    const { db, doc, updateDoc, increment, setDoc } = window.firebaseApp;
                    if (currentUser) {
                        const userRef = doc(db, 'users', currentUser.uid);
                        updateDoc(userRef, {
                            compress_count: increment(1)
                        }).catch(e => console.error("Firebase updateDoc failed:", e));
                    } else if (window.localTrialStatus && window.localTrialStatus.machine_id) {
                        const deviceRef = doc(db, 'users', window.localTrialStatus.machine_id);
                        setDoc(deviceRef, {
                            compress_count: increment(1),
                            last_active: new Date().toISOString(),
                            is_anonymous: true,
                            hostname: window.localTrialStatus.hostname || 'Unknown'
                        }, { merge: true }).catch(e => console.error("Firebase setDoc failed:", e));
                    }
                } catch (dbErr) {
                    console.error("Failed to update compress count in Firebase:", dbErr);
                }
                
            } catch (e) {
                alert("Error: " + e.message);
            } finally {
                progressCompress.classList.add('hidden');
                btnCompress.disabled = false;
            }
        });
    }

});
