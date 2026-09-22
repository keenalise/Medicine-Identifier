// ============================================================================
// App.js
//
// WHAT THIS FILE DOES (in plain words):
// This is the very first thing that runs when the app opens. Similar job
// to the web app's app/layout.tsx: it loads the Baloo 2 font (same font
// as the web version, for a consistent look) and wraps the whole app in
// the language system, before showing the home screen.
//
// While the font is still loading (a brief moment), we show nothing
// rather than flashing text in the wrong font first.
// ============================================================================

import { useCallback } from "react";
import { View, Text, StyleSheet } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import {
  useFonts,
  Baloo2_500Medium,
  Baloo2_600SemiBold,
  Baloo2_700Bold,
  Baloo2_800ExtraBold,
} from "@expo-google-fonts/baloo-2";

import { LanguageProvider } from "./src/LanguageContext";
import HomeScreen from "./src/screens/HomeScreen";

// Keeps the native splash screen visible until we've finished loading
// fonts, so the user never sees a flash of default-font text before Baloo
// 2 is ready.
SplashScreen.preventAutoHideAsync();

// PRAGMATIC DESIGN CHOICE: React Native has no equivalent of CSS's
// "set the font for the whole page once" - every <Text> normally needs
// its own fontFamily. Setting it here, once, on Text's defaultProps means
// every <Text> in the app automatically uses Baloo 2 unless a component
// explicitly overrides it - saving us from repeating `fontFamily:
// "Baloo2_..."` in every single style object across the app.
Text.defaultProps = Text.defaultProps || {};
Text.defaultProps.style = [
  { fontFamily: "Baloo2_600SemiBold" },
  Text.defaultProps.style,
];

export default function App() {
  const [fontsLoaded] = useFonts({
    Baloo2_500Medium,
    Baloo2_600SemiBold,
    Baloo2_700Bold,
    Baloo2_800ExtraBold,
  });

  const onLayoutRootView = useCallback(async () => {
    if (fontsLoaded) {
      // Now that the font we need is ready, it's safe to hide the splash
      // screen and reveal the real app.
      await SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    // Render nothing - the native splash screen is still covering the
    // screen at this point, so this is invisible to the user anyway.
    return null;
  }

  return (
    <View style={styles.root} onLayout={onLayoutRootView}>
      <StatusBar style="light" />
      <LanguageProvider>
        <HomeScreen />
      </LanguageProvider>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
});
