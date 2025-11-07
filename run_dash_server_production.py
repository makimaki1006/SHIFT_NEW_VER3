#!/usr/bin/env python3
"""
Production server for ShiftSuite Dash application on Render

このスクリプトは本番環境用のサーバー起動設定を提供します。
Gunicornと組み合わせて使用されます。
"""
import os
import sys
from dash_app import app

# Flask serverをGunicorn用に公開
server = app.server

if __name__ == '__main__':
    # 環境変数からポート番号を取得（Renderが自動設定）
    port = int(os.environ.get('PORT', 8080))

    # デバッグモードかどうかを確認
    debug_mode = os.environ.get('DASH_ENV', 'production') != 'production'

    if debug_mode:
        print("WARNING: Running in debug mode. Not recommended for production!")

    print(f"Starting ShiftSuite Dash Server on port {port}...")
    print(f"Environment: {os.environ.get('DASH_ENV', 'production')}")
    print(f"Debug mode: {debug_mode}")

    # アプリケーション起動
    # 注意: 本番環境ではGunicornがこのserverオブジェクトを使用するため、
    # app.run()は通常呼ばれません。開発環境やテスト用に残しています。
    app.run(
        host='0.0.0.0',  # 全てのネットワークインターフェースでリッスン
        port=port,
        debug=debug_mode,
        dev_tools_hot_reload=False,  # 本番環境ではホットリロード無効
        dev_tools_ui=False,  # 本番環境では開発ツールUI無効
        dev_tools_props_check=False  # 本番環境ではプロパティチェック無効
    )
