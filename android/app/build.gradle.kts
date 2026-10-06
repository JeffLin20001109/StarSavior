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
        // 手機（arm64）與模擬器（x86_64）；OpenCV 的原生庫很大，只放這兩種
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
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
