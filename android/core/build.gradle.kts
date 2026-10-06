// 與平台無關的核心邏輯（事件判斷、比對網站資料、排版、譯文表），從 Windows 版 Python 移植。
// 測試會讀 shared/golden 的預期結果，確保與 Windows 版輸出完全相同。
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("org.jetbrains.kotlin.jvm")
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

val sharedDir = (System.getenv("SHARED_DIR")?.let { file(it) } ?: rootProject.projectDir.resolve("../shared"))

sourceSets {
    main {
        // 繁→簡對照表與 Windows 版共用同一份
        resources.srcDir(layout.buildDirectory.dir("sharedResources"))
    }
}

val copySharedResources by tasks.registering(Copy::class) {
    from(sharedDir.resolve("t2s.json"))
    into(layout.buildDirectory.dir("sharedResources/com/starsavior/helper/core"))
}
tasks.named("processResources") { dependsOn(copySharedResources) }

dependencies {
    api("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    testImplementation(kotlin("test"))
    testImplementation("junit:junit:4.13.2")
}

tasks.test {
    systemProperty("shared.dir", sharedDir.canonicalPath)
    testLogging { events("failed"); showStandardStreams = false; exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
