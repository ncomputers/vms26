const express = require('express');
const path = require('path');
const axios = require('axios');
const qrcode = require('qrcode');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
require('dotenv').config();
const fs = require('fs');

const PORT = process.env.PORT || 3001;
const SHARED_SECRET = process.env.SHARED_SECRET || '';
const SESSION_PATH = process.env.SESSION_PATH || path.join(__dirname, 'sessions');
const VMS21_WEBHOOK_URL = process.env.VMS21_WEBHOOK_URL;
const VMS21_WEBHOOK_TOKEN = process.env.VMS21_WEBHOOK_TOKEN;

fs.mkdirSync(SESSION_PATH, { recursive: true });

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_PATH }),
  puppeteer: { headless: true }
});

let lastQr = null;
let connected = false;
let phoneNumber = null;

client.on('qr', async (qr) => {
  lastQr = await qrcode.toDataURL(qr);
});

client.on('ready', () => {
  connected = true;
  phoneNumber = client.info?.wid?.user || null;
  console.log('WhatsApp client ready', phoneNumber);
});

client.on('message', async (msg) => {
  console.log('Received message from', msg.from, msg.body);
  await forwardToWebhook({ from: msg.from, body: msg.body });
});

client.on('disconnected', (reason) => {
  connected = false;
  console.log('WhatsApp disconnected', reason);
  client.initialize();
});

client.initialize();

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function verifySecret(req, res, next) {
  const secret = req.headers['x-shared-secret'] || req.query.secret;
  if (SHARED_SECRET && secret !== SHARED_SECRET) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
}

async function forwardToWebhook(payload) {
  if (!VMS21_WEBHOOK_URL) return;
  try {
    await axios.post(VMS21_WEBHOOK_URL, payload, {
      headers: { Authorization: `Bearer ${VMS21_WEBHOOK_TOKEN}` }
    });
    console.log('Forwarded message to VMS21', payload);
  } catch (err) {
    console.error('Failed to forward message', err.message);
  }
}

app.post('/sendText', verifySecret, async (req, res) => {
  const { to, message } = req.body;
  try {
    const response = await client.sendMessage(to, message);
    console.log('Sent text', to, message);
    res.json({ id: response.id._serialized });
  } catch (err) {
    console.error('Send text error', err.message);
    res.status(500).json({ error: 'failed to send' });
  }
});

app.post('/sendMedia', verifySecret, async (req, res) => {
  const { to, fileUrl } = req.body;
  try {
    const media = await MessageMedia.fromUrl(fileUrl);
    await client.sendMessage(to, media);
    console.log('Sent media', to, fileUrl);
    res.json({ status: 'ok' });
  } catch (err) {
    console.error('Send media error', err.message);
    res.status(500).json({ error: 'failed to send' });
  }
});

app.post('/receiveWebhook', verifySecret, async (req, res) => {
  await forwardToWebhook(req.body);
  res.sendStatus(200);
});

app.get('/status', verifySecret, (req, res) => {
  res.json({ connected, phoneNumber });
});

app.get('/qr', verifySecret, (req, res) => {
  res.json({ qr: lastQr });
});

app.get('/', verifySecret, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`WhatsApp service listening on port ${PORT}`);
});

