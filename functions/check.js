const admin = require('firebase-admin');
admin.initializeApp({
  projectId: 'shielddocs-1f6cd'
});
const db = admin.firestore();

async function check() {
  const orders = await db.collection('orders').get();
  console.log(`Total orders: ${orders.docs.length}`);
  orders.forEach(d => console.log('Order:', d.id, d.data().status, d.data().uid));

  const txns = await db.collection('transactions').get();
  console.log(`Total txns: ${txns.docs.length}`);
  txns.forEach(d => console.log('Txn:', d.id, d.data().type, d.data().amount, d.data().uid));
}

check().catch(console.error);
