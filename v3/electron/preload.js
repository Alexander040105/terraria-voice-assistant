const { contextBridge } = require('electron')

// Expose a minimal API if the renderer ever needs native-only features.
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform
})
