# CoreSynch Android app

A small Android app that opens the live site (https://coresync.co.ke/) inside a WebView. It supports:
- file uploads and downloads (downloads go to the phone's Downloads folder)
- pull-to-refresh
- the back button
- an offline screen with a Retry button
- WhatsApp, `mailto:` and `tel:` links, which open in the matching phone app

The site address is set by `coresynchUrl` in `gradle.properties`.

## Build

Requires JDK 17 and the Android SDK (platform 34, build-tools 34). `local.properties` must contain `sdk.dir=/path/to/android-sdk`.

```
./gradlew assembleDebug      # app/build/outputs/apk/debug/app-debug.apk
./gradlew assembleRelease    # app/build/outputs/apk/release/app-release.apk
```

Release builds are signed only if `keystore.properties` exists next to this file:

```
storeFile=/absolute/path/to/coresynch-release.jks
storePassword=...
keyAlias=coresynch
keyPassword=...
```

Keep the keystore and its passwords safe and out of git. Play Store and sideloaded updates must be signed with the same key.

## Known limitation

Google blocks "Sign in with Google" inside embedded WebViews. Inside the app, users should sign in with email and password.

## Website download button

The site serves the APK at `/app/download/` (the "Get the Android App" button on the home page and the "Android App" link in the footer). The file is `pdf_converter/static/android-app/CoreSynch.apk`. After building a new release, copy `app/build/outputs/apk/release/app-release.apk` over it and deploy. Inside the app itself, the button is hidden: the app's user agent contains `CoreSynchApp`.
