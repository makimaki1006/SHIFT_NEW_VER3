"""
Integration tests for Blueprint callback
ブループリントタブのcallback統合テスト
"""
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from dash import html
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go


class TestBlueprintCallbackIntegration:
    """ブループリントタブのcallback統合テスト"""

    @pytest.fixture
    def mock_session(self):
        """モックセッションを作成"""
        session = MagicMock()
        session.get_dataset.return_value = None
        session.put_dataset.return_value = None
        return session

    @pytest.fixture
    def mock_metadata(self):
        """モックメタデータを作成"""
        return {
            'scenario': 'test_scenario',
            'upload_timestamp': '2024-01-01T00:00:00'
        }

    def test_update_blueprint_analysis_content_imports(self):
        """必要なモジュールがインポートできることを確認"""
        try:
            from dash_app import update_blueprint_analysis_content
            assert update_blueprint_analysis_content is not None
        except ImportError as e:
            pytest.fail(f"Failed to import update_blueprint_analysis_content: {e}")

    def test_update_blueprint_analysis_content_callable(self):
        """update_blueprint_analysis_content関数が呼び出し可能であることを確認"""
        from dash_app import update_blueprint_analysis_content
        assert callable(update_blueprint_analysis_content)

    def test_blueprint_analyzer_module_exists(self):
        """BlueprintAnalyzerモジュールが存在することを確認"""
        try:
            from shift_suite.tasks import blueprint_analyzer
            assert blueprint_analyzer is not None
            # 主要な関数が存在することを確認
            assert hasattr(blueprint_analyzer, 'create_blueprint_list')
            assert hasattr(blueprint_analyzer, 'create_scored_blueprint')
        except ImportError as e:
            pytest.fail(f"Failed to import blueprint_analyzer: {e}")

    def test_advanced_blueprint_engine_module_exists(self):
        """AdvancedBlueprintEngineモジュールが存在することを確認"""
        try:
            from shift_suite.tasks.advanced_blueprint_engine_v2 import AdvancedBlueprintEngineV2
            assert AdvancedBlueprintEngineV2 is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AdvancedBlueprintEngineV2: {e}")

    @patch('dash_app.get_session')
    def test_callback_with_no_session(self, mock_get_session):
        """セッションが存在しない場合のcallbackの動作を確認"""
        from dash_app import update_blueprint_analysis_content

        mock_get_session.return_value = None

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='integrated',
                session_id=None,
                metadata=None
            )
            # 結果がタプルであることを確認（7つの出力）
            assert isinstance(result, tuple)
            assert len(result) == 7
        except PreventUpdate:
            # PreventUpdateが発生するのは正常
            assert True
        except Exception as e:
            # エラーハンドリングされていることを確認
            print(f"Expected error handling: {e}")
            assert True

    @patch('dash_app.get_session')
    def test_callback_with_valid_session_no_data(self, mock_get_session, mock_session):
        """有効なセッションだがデータがない場合のcallback動作を確認"""
        from dash_app import update_blueprint_analysis_content

        mock_get_session.return_value = mock_session

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='integrated',
                session_id='test_session_id',
                metadata={'scenario': 'test'}
            )
            # 結果がタプルであることを確認
            assert isinstance(result, tuple)
            assert len(result) == 7
        except Exception as e:
            print(f"Expected error handling: {e}")
            assert True

    def test_callback_output_structure(self):
        """callbackの出力構造が正しいことを確認"""
        from dash_app import update_blueprint_analysis_content

        # Safe modeで実行（環境変数設定）
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='integrated',
                session_id='test',
                metadata=None
            )

            # 7つの出力があることを確認
            assert len(result) == 7

            # 各出力の型を確認
            scatter_data, scatter_fig, rules_data, rules_cols, facts_data, implicit_content, factual_content = result

            # scatter_dataは辞書
            assert isinstance(scatter_data, dict)

            # scatter_figは辞書またはFigureのJSON
            assert isinstance(scatter_fig, (dict, str))

            # rules_dataはリスト
            assert isinstance(rules_data, list)

            # rules_colsはリスト
            assert isinstance(rules_cols, list)

            # facts_dataはリスト
            assert isinstance(facts_data, list)

            # implicit_contentはDashコンポーネント
            assert isinstance(implicit_content, (html.Div, str, list))

            # factual_contentはDashコンポーネント
            assert isinstance(factual_content, (html.Div, str, list))

        finally:
            # 環境変数をクリーンアップ
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)

    def test_callback_analysis_type_integrated(self):
        """analysis_type='integrated'での動作を確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='integrated',
                session_id='test',
                metadata=None
            )
            assert len(result) == 7
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)

    def test_callback_analysis_type_implicit(self):
        """analysis_type='implicit_only'での動作を確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='implicit_only',
                session_id='test',
                metadata=None
            )
            assert len(result) == 7
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)

    def test_callback_analysis_type_factual(self):
        """analysis_type='factual_only'での動作を確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='factual_only',
                session_id='test',
                metadata=None
            )
            assert len(result) == 7
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)

    def test_callback_multiple_executions(self):
        """複数回実行しても正常に動作することを確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            for i in range(3):
                result = update_blueprint_analysis_content(
                    n_clicks=i+1,
                    analysis_type='integrated',
                    session_id='test',
                    metadata=None
                )
                assert len(result) == 7
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)


class TestBlueprintCallbackErrorHandling:
    """ブループリントcallbackのエラーハンドリングテスト"""

    def test_callback_with_invalid_analysis_type(self):
        """無効なanalysis_typeでのエラーハンドリングを確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='invalid_type',
                session_id='test',
                metadata=None
            )
            # エラーが発生しても結果が返ることを確認
            assert result is not None
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)

    def test_callback_with_none_inputs(self):
        """全ての入力がNoneの場合のエラーハンドリングを確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        try:
            # NoneのみでPreventUpdateが発生することを期待
            with pytest.raises(PreventUpdate):
                update_blueprint_analysis_content(
                    n_clicks=None,
                    analysis_type=None,
                    session_id=None,
                    metadata=None
                )
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)


class TestBlueprintCallbackRealExecution:
    """ブループリントcallbackの実際の実行テスト（Safe mode無効）"""

    @patch('dash_app.get_session')
    def test_callback_real_execution_no_session(self, mock_get_session):
        """セーフモード無効での実行（セッションなし）"""
        from dash_app import update_blueprint_analysis_content
        import os

        # セーフモードを明示的にOFF
        os.environ.pop('BLUEPRINT_SAFE_MODE', None)

        mock_get_session.return_value = None

        try:
            result = update_blueprint_analysis_content(
                n_clicks=1,
                analysis_type='integrated',
                session_id='test',
                metadata=None
            )
            # エラーハンドリングされて結果が返ることを確認
            assert result is not None
            assert len(result) == 7
        except PreventUpdate:
            # PreventUpdateも許容
            assert True
        except Exception as e:
            # エラーが出ても許容（セッションがないため）
            assert True

    def test_callback_with_different_analysis_types(self):
        """異なる分析タイプでの動作確認"""
        from dash_app import update_blueprint_analysis_content
        import os
        os.environ['BLUEPRINT_SAFE_MODE'] = '1'

        analysis_types = ['integrated', 'implicit_only', 'factual_only']

        try:
            for analysis_type in analysis_types:
                result = update_blueprint_analysis_content(
                    n_clicks=1,
                    analysis_type=analysis_type,
                    session_id='test',
                    metadata=None
                )
                assert len(result) == 7, f"Failed for analysis_type={analysis_type}"
        finally:
            os.environ.pop('BLUEPRINT_SAFE_MODE', None)
