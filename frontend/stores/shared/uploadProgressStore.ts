"use client";

import { create } from "zustand";

interface UploadProgressStore {
  progress: number;
  isUploading: boolean;
  setProgress: (progress: number) => void;
  startUpload: () => void;
  finishUpload: () => void;
}

export const useUploadProgressStore = create<UploadProgressStore>((set) => ({
  progress: 0,
  isUploading: false,

  setProgress: (progress: number) => set({ progress }),

  startUpload: () => set({ isUploading: true, progress: 0 }),

  finishUpload: () => set({ isUploading: false, progress: 0 }),
}));
