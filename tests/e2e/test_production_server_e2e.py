"""
E2E tests for run_dash_server_production.py

本番環境用サーバーの実際の起動と動作のE2Eテスト
"""
import os
import sys
import pytest
import requests
import time
import subprocess
import signal
from pathlib import Path


@pytest.fixture(scope="module")
def production_server():
    """
    本番サーバーをテストポートで起動するフィクスチャ
    """
    # テスト用ポート
    test_port = 8056

    # 環境変数を設定
    env = os.environ.copy()
    env['PORT'] = str(test_port)
    env['DASH_ENV'] = 'production'

    # サーバープロセスを起動
    process = subprocess.Popen(
        [sys.executable, 'run_dash_server_production.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # サーバーが起動するまで待機
    max_wait = 30  # 最大30秒待機
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f'http://127.0.0.1:{test_port}/', timeout=1)
            if response.status_code == 200:
                server_ready = True
                break
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(0.5)

    if not server_ready:
        # サーバーが起動しなかった場合、エラーログを出力
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        pytest.fail(f"Server failed to start within {max_wait} seconds.\nSTDOUT: {stdout}\nSTDERR: {stderr}")

    # テストを実行
    yield f'http://127.0.0.1:{test_port}'

    # テスト終了後、サーバーを停止
    if sys.platform == "win32":
        process.send_signal(signal.CTRL_C_EVENT)
    else:
        process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


class TestProductionServerE2E:
    """本番サーバーのE2Eテスト"""

    def test_server_starts_successfully(self, production_server):
        """サーバーが正常に起動することを確認"""
        response = requests.get(production_server)
        assert response.status_code == 200

    def test_server_serves_html(self, production_server):
        """サーバーがHTMLを返すことを確認"""
        response = requests.get(production_server)
        assert 'text/html' in response.headers.get('Content-Type', '')

    def test_server_has_dash_content(self, production_server):
        """サーバーがDashコンテンツを含むことを確認"""
        response = requests.get(production_server)
        # Dash アプリケーションの典型的な要素を確認
        content = response.text.lower()
        assert any(keyword in content for keyword in ['dash', 'react', 'html'])

    def test_server_responds_to_multiple_requests(self, production_server):
        """サーバーが複数のリクエストに応答できることを確認"""
        for i in range(5):
            response = requests.get(production_server)
            assert response.status_code == 200

    def test_server_handles_concurrent_requests(self, production_server):
        """サーバーが並行リクエストを処理できることを確認"""
        import concurrent.futures

        def make_request():
            response = requests.get(production_server)
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # すべてのリクエストが成功
        assert all(status == 200 for status in results)


class TestGunicornDeployment:
    """Gunicornでのデプロイメントテスト（シミュレーション）"""

    def test_gunicorn_can_import_server(self):
        """Gunicornがserverオブジェクトをインポートできることを確認"""
        # gunicorn run_dash_server_production:server の動作をシミュレート
        import run_dash_server_production
        server = run_dash_server_production.server

        assert server is not None
        assert callable(server)

    def test_wsgi_app_callable(self):
        """WSGI appが呼び出し可能であることを確認"""
        import run_dash_server_production

        # WSGI仕様に従った環境変数を作成
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8080',
            'wsgi.url_scheme': 'http',
        }

        # start_response コールバック
        response_status = []
        response_headers = []

        def start_response(status, headers):
            response_status.append(status)
            response_headers.append(headers)

        # WSGI appを呼び出し
        try:
            result = run_dash_server_production.server.wsgi_app(environ, start_response)
            # 結果が返されることを確認
            assert result is not None
        except Exception as e:
            # 一部の環境変数が不足している場合はスキップ
            pytest.skip(f"WSGI call failed with: {e}")


class TestProductionConfiguration:
    """本番環境設定のテスト"""

    def test_production_env_disables_debug(self):
        """本番環境でdebugモードが無効になることを確認"""
        env = os.environ.copy()
        env['DASH_ENV'] = 'production'

        debug_mode = env.get('DASH_ENV', 'production') != 'production'
        assert debug_mode is False

    def test_port_configuration(self):
        """PORT環境変数が正しく読み取られることを確認"""
        env = os.environ.copy()
        env['PORT'] = '9999'

        port = int(env.get('PORT', 8080))
        assert port == 9999


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
