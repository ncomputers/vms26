# Configuration

## apk_build.json

Defines settings used when building the mobile Android application.

- **appName**: Display name of the app.
- **appId**: Unique Android package identifier.
- **serverUrl**: Base URL the app will communicate with.
- **versionName**: Human readable release version.
- **versionCode**: Incremental integer used by Android for upgrades.
- **icons**: Mapping of platform names to icon asset paths.
- **permissions**: Android permissions the app requests.
- **signing**: Credentials for signing the APK.
  - **keystorePath**: Path to the keystore file.
  - **alias**: Alias of the key within the keystore.
  - **storePassword**: Password protecting the keystore.
  - **keyPassword**: Password for the key alias.
