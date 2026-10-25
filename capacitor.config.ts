import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.aircontrol.remote',
  appName: 'AirControl',
  webDir: 'www',
  server: {
    androidScheme: 'http',
    cleartext: true
  }
};

export default config;
