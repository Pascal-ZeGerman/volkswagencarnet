# US VW CarNet Network Traffic Analysis Guide

If the PKCE implementation doesn't work, you'll need to capture the actual OAuth flow from the official VW Car-Net app to get current 2026 credentials.

## Prerequisites

### Option A: Android Device/Emulator (Recommended)
- Android phone or Android emulator (Android Studio)
- mitmproxy or Charles Proxy
- Official VW Car-Net app from Google Play Store

### Option B: iOS Device
- iPhone/iPad with iOS
- Charles Proxy on Mac
- Official VW Car-Net app from App Store

## Method 1: Using mitmproxy (Free, Command Line)

### Step 1: Install mitmproxy

```bash
# macOS
brew install mitmproxy

# Linux
pip install mitmproxy

# Windows
# Download from: https://mitmproxy.org/
```

### Step 2: Start mitmproxy

```bash
mitmweb
```

This opens a web interface at `http://localhost:8081`

### Step 3: Configure Android Device

**On Android:**
1. Go to Settings → Wi-Fi
2. Long-press your Wi-Fi network → Modify
3. Advanced Options → Proxy → Manual
4. Proxy hostname: `<your-computer-ip>` (e.g., 192.168.1.100)
5. Proxy port: `8080`
6. Save

**On Computer:**
Find your IP:
```bash
# macOS/Linux
ifconfig | grep "inet "

# Windows
ipconfig
```

### Step 4: Install mitmproxy Certificate

**On Android:**
1. Open browser on phone
2. Navigate to: `http://mitm.it`
3. Download Android certificate
4. Install certificate:
   - Settings → Security → Install from storage
   - Select downloaded certificate
   - Name it "mitmproxy"

### Step 5: Capture VW App Traffic

1. Open VW Car-Net app on phone
2. Log out if already logged in
3. Start fresh login
4. Watch mitmproxy web interface at http://localhost:8081

### Step 6: Find OAuth Credentials

Look for these requests:

**1. Authorization Request**
```
GET https://<endpoint>/oidc/v1/authorize
```

Look for these parameters:
- `client_id=<US_CLIENT_ID>` ← **This is what we need!**
- `code_challenge=...`
- `code_challenge_method=S256`
- `scope=...`
- `redirect_uri=...`

**2. Token Exchange Request**
```
POST https://<endpoint>/oidc/v1/token
```

Look for these in the request body:
- `client_id=<US_CLIENT_ID>` ← **Confirm it matches!**
- `code_verifier=...`
- `grant_type=authorization_code`

**3. Base API Endpoint**

Note the domain used in all requests:
- Example: `https://b-h-s.spr.us00.p.con-veh.net`
- Or: `https://na.bff.cariad.digital`

### Step 7: Extract Information

From the captured traffic, extract:

```python
# What to report back:
US_CLIENT_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx@apps_vw-dilab_com"
US_BASE_API = "https://discovered-endpoint.com"
US_SCOPE = "openid profile ..."  # If different from EU
US_REDIRECT_URI = "car-net://..."  # If different from EU
```

## Method 2: Using Charles Proxy (GUI, Easier)

### Step 1: Install Charles Proxy

Download from: https://www.charlesproxy.com/

### Step 2: Configure SSL Proxying

1. Charles → Proxy → SSL Proxying Settings
2. Add location: `*` (all hosts)
3. Enable SSL Proxying

### Step 3: Configure Mobile Device

**Android/iOS:**
1. Settings → Wi-Fi → Configure Proxy
2. Manual Proxy
3. Server: `<your-computer-ip>`
4. Port: `8888`

### Step 4: Install Charles Certificate

**On mobile device:**
1. Open browser
2. Go to: `http://chls.pro/ssl`
3. Install certificate
4. Trust certificate (iOS: Settings → General → About → Certificate Trust Settings)

### Step 5: Capture & Filter

1. Open VW Car-Net app
2. Log out and log back in
3. In Charles, filter for:
   - `bff.cariad.digital`
   - `con-veh.net`
   - `vw.com`
   - `volkswagen.com`

4. Look for OAuth endpoints (same as mitmproxy method above)

## What to Look For

### Critical Information

1. **Client ID** (highest priority)
   ```
   client_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx@apps_vw-dilab_com
   ```

2. **Base API Endpoint**
   ```
   https://b-h-s.spr.us00.p.con-veh.net
   or
   https://na.bff.cariad.digital
   ```

3. **OAuth Scope** (if different)
   ```
   scope=openid profile badge cars dealers vin ...
   ```

4. **Redirect URI** (if different)
   ```
   redirect_uri=car-net://authenticated
   or
   redirect_uri=weconnect://authenticated
   ```

5. **PKCE Parameters**
   - Verify `code_challenge_method` is `S256`
   - Verify `code_challenge` is present
   - Verify `code_verifier` is sent in token exchange

### Red Flags

If you see any of these, the app may be using a different approach:
- ❌ No `client_id` parameter (client credentials in header instead)
- ❌ Different OAuth flow (implicit grant, client credentials)
- ❌ Custom authentication (not OAuth2)
- ❌ Certificate pinning preventing capture

## Troubleshooting

### Certificate Errors on Android

**Android 7+** requires apps to explicitly trust user certificates.

**Solution 1: Root your Android** (if comfortable)
```bash
# With root access, install cert as system cert
```

**Solution 2: Use Android emulator**
- Android Studio AVD
- Can easily install system certificates

**Solution 3: Modify VW APK**
- Decompile APK with apktool
- Modify network_security_config.xml to trust user certs
- Recompile and install

### iOS Certificate Pinning

VW app may use certificate pinning on iOS.

**Solution: Use Android instead**
Android is generally easier for traffic analysis.

### No Traffic Captured

**Check:**
1. Proxy is running (8080 or 8888)
2. Phone is on same Wi-Fi network
3. Phone proxy is configured correctly
4. Certificate is installed and trusted
5. Try restarting both phone and proxy

### App Detects Proxy

Some apps detect and refuse to work with proxies.

**Try:**
1. Different device
2. Older version of VW app (APKMirror.com)
3. Rooted device with Frida/Xposed to bypass detection

## Report Your Findings

Once you've captured the traffic, report back with:

```markdown
## US VW CarNet OAuth Credentials (2026)

**Client ID:**
`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx@apps_vw-dilab_com`

**Base API:**
`https://discovered-endpoint.com`

**Authorization Endpoint:**
`https://discovered-endpoint.com/oidc/v1/authorize`

**Token Endpoint:**
`https://discovered-endpoint.com/oidc/v1/token`

**Scope:**
`openid profile badge cars dealers vin`

**Redirect URI:**
`car-net://authenticated`

**PKCE:**
- code_challenge_method: S256
- Uses PKCE: Yes

**Additional Parameters:**
- Any other parameters you notice in the OAuth flow
```

This will allow us to update the library with current 2026 credentials!

## Alternative: Ask the Community

If traffic analysis is too complex:

1. **GitHub Issue**: https://github.com/robinostlund/volkswagencarnet/issues
   - Ask if anyone has 2026 credentials

2. **Home Assistant Community**: https://community.home-assistant.io/
   - Search for "VW CarNet US"

3. **Reddit**: r/homeassistant, r/Volkswagen
   - Ask about US integration

Someone else may have already done the analysis!
