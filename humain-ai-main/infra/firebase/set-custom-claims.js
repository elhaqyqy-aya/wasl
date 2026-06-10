/**
 * set-custom-claims.js
 * 
 * Script to assign custom user claims (roles) via the Firebase Admin SDK.
 * 
 * Usage:
 *   node set-custom-claims.js <uid> <role>
 * 
 * Roles: 'collaborateur', 'manager', 'rh', 'direction', 'admin', 'qvt'
 */

const admin = require('firebase-admin');

// Ensure service account credentials are provided via environment variables or file
const serviceAccountPath = process.env.FIREBASE_SERVICE_ACCOUNT_KEY_PATH;

if (!serviceAccountPath) {
  console.error("Error: FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable is not set.");
  process.exit(1);
}

try {
  const serviceAccount = require(serviceAccountPath);
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
  });
} catch (err) {
  console.error("Failed to initialize Firebase Admin SDK:", err.message);
  process.exit(1);
}

const uid = process.argv[2];
const role = process.argv[3];

const validRoles = ['collaborateur', 'manager', 'rh', 'direction', 'admin', 'qvt'];

if (!uid || !role) {
  console.log("Usage: node set-custom-claims.js <uid> <role>");
  process.exit(1);
}

if (!validRoles.includes(role)) {
  console.error(`Error: Invalid role. Must be one of: ${validRoles.join(', ')}`);
  process.exit(1);
}

async function setClaims(uid, role) {
  try {
    const user = await admin.auth().getUser(uid);
    console.log(`Found user: ${user.email} (UID: ${user.uid})`);
    
    // Set custom claims
    await admin.auth().setCustomUserClaims(uid, { role: role });
    
    // Retrieve and print updated user
    const updatedUser = await admin.auth().getUser(uid);
    console.log(`Successfully updated custom claims:`, updatedUser.customClaims);
  } catch (error) {
    console.error("Error setting custom claims:", error.message);
    process.exit(1);
  }
}

setClaims(uid, role);
