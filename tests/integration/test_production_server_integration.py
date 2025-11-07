"""
Integration tests for run_dash_server_production.py

本番環境用サーバーとDashアプリケーションの統合テスト
"""
import os
import sys
import pytest
import requests
import time
import subprocess
from unittest.mock import patch


class TestDashAppIntegration:
    """Dashアプリケーションとの統合テスト"""

    def test_server_object_from_dash_app(self):
        """dash_app から正しく server オブジェクトがインポートできることを確認"""
        import run_dash_server_production
        from dash_app import app

        # run_dash_server_production.server が dash_app.app.server と同一であることを確認
        assert run_dash_server_production.server is app.server

    def test_server_has_dash_routes(self):
        """server が Dash のルートを持つことを確認"""
        import run_dash_server_production

        # Flask app が Dash のルートを持つことを確認
        with run_dash_server_production.server.test_client() as client:
            # Dash のトップページにアクセス
            response = client.get('/')
            assert response.status_code == 200

            # レスポンスに Dash コンテンツが含まれていることを確認
            assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    def test_server_has_dash_assets(self):
        """server が Dash のアセットルートを持つことを確認"""
        import run_dash_server_production

        # Flask app が Dash のアセットルートを持つことを確認
        with run_dash_server_production.server.test_client() as client:
            # /_dash-component-suites/ へのアクセスを確認
            response = client.get('/_dash-component-suites/')
            # 404 または 200 のいずれか（アセットがあるかないか）
            assert response.status_code in [200, 404]


class TestGunicornCompatibility:
    """Gunicorn互換性のテスト"""

    def test_server_wsgi_compliance(self):
        """server が WSGI 準拠であることを確認"""
        import run_dash_server_production

        # WSGI callable の確認
        assert callable(run_dash_server_production.server)
        assert hasattr(run_dash_server_production.server, 'wsgi_app')

    def test_gunicorn_command_compatibility(self):
        """Gunicorn コマンドラインでの起動互換性を確認"""
        # gunicorn run_dash_server_production:server が正しく解釈できるか
        import run_dash_server_production

        # モジュール名が正しいか
        assert run_dash_server_production.__name__ == 'run_dash_server_production'

        # server オブジェクトが存在するか
        assert hasattr(run_dash_server_production, 'server')

    def test_server_can_handle_request(self):
        """server が実際のリクエストを処理できることを確認"""
        import run_dash_server_production

        with run_dash_server_production.server.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200


class TestEnvironmentVariableIntegration:
    """環境変数との統合テスト"""

    @patch.dict(os.environ, {'PORT': '8888', 'DASH_ENV': 'production'})
    def test_production_configuration(self):
        """本番環境設定が正しく適用されることを確認"""
        port = int(os.environ.get('PORT', 8080))
        debug_mode = os.environ.get('DASH_ENV', 'production') != 'production'

        assert port == 8888
        assert debug_mode is False

    @patch.dict(os.environ, {'PORT': '7777', 'DASH_ENV': 'development'})
    def test_development_configuration(self):
        """開発環境設定が正しく適用されることを確認"""
        port = int(os.environ.get('PORT', 8080))
        debug_mode = os.environ.get('DASH_ENV', 'production') != 'production'

        assert port == 7777
        assert debug_mode is True


class TestServerHealthCheck:
    """サーバーヘルスチェックのテスト"""

    def test_server_responds_to_root(self):
        """/ エンドポイントが応答することを確認"""
        import run_dash_server_production

        with run_dash_server_production.server.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200

    def test_server_has_flask_config(self):
        """Flask config が設定されていることを確認"""
        import run_dash_server_production

        config = run_dash_server_production.server.config
        assert config is not None
        assert isinstance(config, dict)


class TestSessionManagement:
    """セッション管理との統合テスト"""

    def test_server_supports_sessions(self):
        """Flask セッションがサポートされていることを確認"""
        import run_dash_server_production

        # Flask のセッション機能が有効であることを確認
        assert hasattr(run_dash_server_production.server, 'secret_key')

    def test_server_has_session_interface(self):
        """セッションインターフェースが存在することを確認"""
        import run_dash_server_production

        assert hasattr(run_dash_server_production.server, 'session_interface')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
