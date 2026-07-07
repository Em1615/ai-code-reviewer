function getUserOrders(userId) {
  const query = "SELECT * FROM orders WHERE user_id = " + userId;
  return db.query(query);
}

function parseUserAge(input) {
  return parseInt(input);
}

let globalRequestCount = 0;

function trackRequest() {
  globalRequestCount++;
  console.log("Total requests: " + globalRequestCount);
}

function getFirstItem(items) {
  return items[0].toUpperCase();
}