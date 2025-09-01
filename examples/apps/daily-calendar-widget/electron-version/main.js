const { app, BrowserWindow, Tray, Menu, screen, ipcMain } = require('electron');
const path = require('path');

let mainWindow;
let tray = null;
let isAlwaysOnTop = true;

function createWindow() {
  // スクリーンサイズを取得
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  // ウィンドウを作成
  mainWindow = new BrowserWindow({
    width: 220,
    height: 250,
    x: width - 240,  // 画面右下に配置
    y: height - 280,
    frame: false,     // フレームなし
    transparent: true, // 透明背景
    resizable: false,
    alwaysOnTop: isAlwaysOnTop,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    icon: path.join(__dirname, 'icon.png')
  });

  // HTMLファイルを読み込み
  mainWindow.loadFile('index.html');

  // 開発者ツールを開く（デバッグ用）
  // mainWindow.webContents.openDevTools();

  // ウィンドウが閉じられたときの処理
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // システムトレイの作成
  createTray();
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'icon.png'));
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '表示/非表示',
      click: () => {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
        }
      }
    },
    {
      label: '最前面表示',
      type: 'checkbox',
      checked: isAlwaysOnTop,
      click: (menuItem) => {
        isAlwaysOnTop = menuItem.checked;
        mainWindow.setAlwaysOnTop(isAlwaysOnTop);
      }
    },
    {
      label: '位置をリセット',
      click: () => {
        const { width, height } = screen.getPrimaryDisplay().workAreaSize;
        mainWindow.setPosition(width - 240, height - 280);
      }
    },
    { type: 'separator' },
    {
      label: '設定',
      click: () => {
        // 設定ウィンドウを開く
        createSettingsWindow();
      }
    },
    { type: 'separator' },
    {
      label: '終了',
      click: () => {
        app.quit();
      }
    }
  ]);

  tray.setToolTip('日めくりカレンダー');
  tray.setContextMenu(contextMenu);

  // トレイアイコンをクリックしたときの処理
  tray.on('click', () => {
    mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
  });
}

function createSettingsWindow() {
  const settingsWindow = new BrowserWindow({
    width: 400,
    height: 500,
    parent: mainWindow,
    modal: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  settingsWindow.loadFile('settings.html');
}

// IPCハンドラー
ipcMain.on('minimize-window', () => {
  mainWindow.minimize();
});

ipcMain.on('close-window', () => {
  app.quit();
});

ipcMain.on('toggle-always-on-top', () => {
  isAlwaysOnTop = !isAlwaysOnTop;
  mainWindow.setAlwaysOnTop(isAlwaysOnTop);
});

// アプリケーションの準備が完了したらウィンドウを作成
app.whenReady().then(createWindow);

// すべてのウィンドウが閉じられたときの処理
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// アプリケーションがアクティブになったときの処理（macOS）
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// 単一インスタンスを強制
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    // 既存のインスタンスにフォーカス
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}