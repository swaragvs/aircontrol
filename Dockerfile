FROM eclipse-temurin:21-jdk-jammy

ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH="${PATH}:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip xz-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22 for Vite and Capacitor
RUN curl -fsSLO https://nodejs.org/dist/v22.16.0/node-v22.16.0-linux-x64.tar.xz \
    && mkdir -p /opt/node \
    && tar -xJf node-v22.16.0-linux-x64.tar.xz -C /opt/node --strip-components=1 \
    && rm node-v22.16.0-linux-x64.tar.xz

ENV PATH="/opt/node/bin:${PATH}"

# Install Android SDK command-line tools
RUN mkdir -p "${ANDROID_HOME}/cmdline-tools" \
    && curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip -o /tmp/android-tools.zip \
    && unzip -q /tmp/android-tools.zip -d /tmp/android-tools \
    && mv /tmp/android-tools/cmdline-tools "${ANDROID_HOME}/cmdline-tools/latest" \
    && rm -rf /tmp/android-tools /tmp/android-tools.zip \
    && yes | sdkmanager --licenses >/dev/null 2>&1 || true

RUN sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"
