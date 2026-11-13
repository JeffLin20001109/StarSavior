plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.starsavior.helper"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.starsavior.helper"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // 正式版（GitHub Actions 的 main 分支）寫入 commit，啟動畫面用來檢查有沒有新版本；其他情況留空、不檢查
        val official = System.getenv("GITHUB_REF") == "refs/heads/main" && System.getenv("GITHUB_EVENT_NAME") != "pull_request"
        buildConfigField("String", "BUILD_COMMIT", "\"${if (official) System.getenv("GITHUB_SHA") ?: "" else ""}\"")
    }

    buildFeatures { buildConfig = true }

    // 依 ABI 分開打包：手機用 arm64（正式版的 StarSaviorJourneyHelper.apk），模擬器測試用 x86_64。
    // OpenCV 的原生庫很大，每種 ABI 一份；分開後手機版的 APK 小很多。
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "x86_64")
            isUniversalApk = false
        }
    }

    // 固定的簽章金鑰：正式版每次都要用同一把，手機才能直接覆蓋安裝（App 內更新）。
    // CI 從 GitHub Secrets 解出金鑰檔並設定這些環境變數；沒有設定時（本機、PR）用預設的除錯金鑰。
    val keystore = System.getenv("ANDROID_KEYSTORE_FILE")?.let { file(it) }?.takeIf { it.exists() }
    val fixedSigning = keystore?.let { store ->
        signingConfigs.create("fixed") {
            storeFile = store
            storeType = "pkcs12"
            storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("ANDROID_KEY_ALIAS")
            keyPassword = System.getenv("ANDROID_KEY_PASSWORD") ?: System.getenv("ANDROID_KEYSTORE_PASSWORD")
        }
    }

    buildTypes {
        debug {
            if (fixedSigning != null) signingConfig = fixedSigning
        }
        release {
            isMinifyEnabled = false
            signingConfig = fixedSigning ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("sharedAssets"))
    // 模擬器測試用 shared/fixtures 的遊戲截圖（與 Windows 版相同）
    sourceSets["androidTest"].assets.srcDir(rootProject.projectDir.resolve("../shared/fixtures"))
    sourceSets["androidTest"].assets.srcDir(rootProject.projectDir.resolve("../shared/golden"))
}

// 內建一份譯文表（離線時使用）；與 Windows 版共用 shared/translations_zh.json
val copySharedAssets by tasks.registering(Copy::class) {
    from(rootProject.projectDir.resolve("../shared/translations_zh.json"))
    into(layout.buildDirectory.dir("sharedAssets"))
}
tasks.named("preBuild") { dependsOn(copySharedAssets) }

dependencies {
    implementation(project(":core"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    implementation("org.opencv:opencv:4.10.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}
