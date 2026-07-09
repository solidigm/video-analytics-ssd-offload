// Created by Metrum AI for Solidigm

import { configureStore } from '@reduxjs/toolkit'

// Redux store configuration
// Feature slices will be added here as the app grows
// Structure: features/{featureName}/{featureName}Slice.ts

export const store = configureStore({
  reducer: {
    // Add feature slices here:
    // inference: inferenceReducer,
    // analytics: analyticsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: false,
    }),
  devTools: import.meta.env.DEV,
})

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
