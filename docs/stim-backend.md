# device-gateway への stim (Clifford) シミュレータバックエンド追加

## 実施サマリー

device-gateway のシミュレータ（従来 qulacs のみ）に **stim**（Clifford 型シミュレータ）を追加した。
stim はクリフォード回路専用のため、非クリフォードゲートは **警告ログを書いて無視**する（例外を投げない）。
実装は `develop` から切った **`feature/stim-backend`** ブランチで行い、ent（oqtopus-cli 環境）へのデプロイとエンドツーエンド検証まで完了した。

- 実施日: 2026-09-09
- ブランチ: `feature/stim-backend`（コミット `6b98e38`）
- 対象リポジトリ: `oqtopus-team/device-gateway`

---

## 1. 背景と設計方針

### ゲートサポート方針

oqtopus は tranqu で **`rz/sx/cx` ベーシス**にトランスパイルする。そのため `sx` と `rz(±π/2)→S/S_DAG` をサポートしないと oqtopus-cli 経由の実回路で結果が壊れる。

| カテゴリ | Qiskit ゲート | stim ゲート | 扱い |
|---|---|---|---|
| サポート | `x`, `h`, `sx`, `z`, `cx` | `X`, `H`, `SQRT_X`, `Z`, `CX` | 適用 |
| サポート | `rz(π/2)` / `rz(-π/2)` | `S` / `S_DAG` | 適用（±π/2 のみ） |
| サポート | `rz(π)` / `rz(-π)` | `Z` | 適用 |
| no-op | `measure`, `barrier`, `delay` | — | スキップ（measure は backend が末尾に追加） |
| 非対応 | `y`, `s`, `sdg`, `sxdg`, `cz`, `swap`, `t`, `tdg`, `rx`, `ry`, `rz(それ以外)`, `p`, `u1`, `u2`, `u3`, `ccx` 等 | — | **警告ログを書いて無視**（例外を投げない） |

### 実装のポイント

- **物理インデックス写像**: qulacs compiler と同様、qiskit の論理 qubit index を backend の `physical_label_to_physical_index` で物理 index に写像する。
- **末尾サンプリング**: 測定は全ゲートの後（end-of-circuit sampling）に追加する。qulacs バックエンドのセマンティクスと一致。
- **count key 順序**: qulacs の `"".join(new_bits)[::-1]`（clbit 反転）と同じ規約を使い、qulacs と結果を一致させる。
- **未測定 clbit**: すべて "0" として扱う（qulacs と同じ挙動）。
- **非クリフォード角度の判定**: `_RZ_ANGLE_TOLERANCE = 1e-9` の `math.isclose` で ±π/2, ±π のみクリフォードと判定。

---

## 2. 変更ファイル

### 新規
- `src/device_gateway/plugins/stim/__init__.py` — 空
- `src/device_gateway/plugins/stim/compiler.py` — `StimCompiler`（Qiskit 回路 → stim.Circuit）
- `src/device_gateway/plugins/stim/backend.py` — `StimBackend(BaseBackend)`（execute / measure_map / サンプリング）
- `tests/device_gateway/plugins/stim/test_stim_backend.py` — 12 テスト
- `config/config.yaml.stim` — `default_backend: stim` の設定例

### 変更
- `pyproject.toml` — `stim>=1.14` を依存に追加
- `uv.lock` — 更新（stim 1.16.0 解決）
- `config/config.yaml.qulacs` / `config/config.yaml.qubex` / `config/example/config.yaml` — `stim` エントリ追加、`default_backend` コメント更新

### テスト（tests/device_gateway/plugins/stim/test_stim_backend.py）
`pytest.importorskip("stim")` を使用。4 量子ビットトポロジーで以下を検証:
- Bell 状態（h, cx）→ {00, 11}
- x でフリップ → {"1": shots}
- h / sx で重ね合わせ
- rz(π/2) → S、S*S=Z の等価性
- 非クリフォード（t, rx 等）→ 警告ログ＆無視、実行は成功
- barrier / delay → no-op
- 未測定 clbit は 0、measure の clbit 再割当
- トポロジー外 qubit index → KeyError（qulacs と同様）

---

## 3. 検証結果（ローカル）

| チェック | 結果 |
|---|---|
| `uv run ruff check` | ✅ All checks passed |
| `uv run ruff format --check` | ✅ 自分のファイルは通過（`docs/example/*.ipynb` 3 件は既存の未フォーマットで変更なし） |
| `uv run mypy` | ✅ stim 関連は Success（`src/tool/generate_device_topology.py` の yaml スタブエラーは既存、コミット 096e541 由来で未変更） |
| `uv run pytest` | ✅ 52 passed, 1 skipped（qubex 未インストール） |

---

## 4. ent（oqtopus-cli 環境）へのデプロイ

### 確認した前提
- ent 上の gateway config は **DI 方式**（`default_backend` + `backend_di_container.registry`）→ stim プラグインをそのまま追加可能。
- gateway はネイティブプロセスとして `uv run --project <release> python -m device_gateway.service ...` で起動。
- デプロイは oqtopus-cli が GitHub `oqtopus-team/device-gateway` からソースを取得し `uv sync --frozen --no-dev` する仕組み。
- PyPI 到達可（stim 取得可能）、`uv` は `/home/tmori/.local/bin/uv`、トポロジーは 16 量子ビット（`device_id: "qulacs"`）。

### 実行手順
```bash
# ① push（ローカル）
git push -u origin feature/stim-backend

# ② ent で install（login shell + my-backend ディレクトリで実行）
bash -lc "cd /home/tmori/work/oqtopus/my-backend && bash /home/tmori/work/oqtopus/oqtopus-cli/bin/oqtopus backend install gateway branch:feature/stim-backend"

# ③ config 変更（default_backend: stim に、stim エントリ追加）※事前バックアップ
# ④ 再起動
bash -lc "cd /home/tmori/work/oqtopus/my-backend && bash /home/tmori/work/oqtopus/oqtopus-cli/bin/oqtopus backend restart gateway"
```

- install 後: `my-backend/gateway` に展開、`stim==1.16.0` 導入、binding `gateway=branch:feature/stim-backend`。
- 変更前 config: `config/gateway/config.yaml.bak_pre_stim`。

### 注意点（デプロイ時の罠）
- oqtopus bin は実行権限がないため `bash <path>` で実行する。
- ログインシェル（`bash -lc`）は `$HOME` に cwd が戻るため、`cd` をログインシェル内で行う。
- 非ログイン ssh シェルには `uv` が PATH にない。
- `uv sync --frozen` を使うため、push する `uv.lock` と `pyproject.toml` の整合が必須。

---

## 5. エンドツーエンド検証（ent 上）

クライアント（sample/examples）→ クラウド API（localhost:8080）→ gateway（stim バックエンド）の全スタックで検証。

| ケース | 結果 |
|---|---|
| **Bell 状態**（h, cx, measure, 10000 shots） | ✅ `{00: 4943, 11: 5057}` — 期待通りの Bell 状態。トランスパイル後 `rz(pi/2), sx, rz(pi/2), cx` ベーシスを stim が正しく処理 |
| **非クリフォード**（t ゲート, 1000 shots） | ✅ ジョブは **succeeded**、counts `{0: 1000}`（T ゲートは無視）。ログに `WARNING ... "Unsupported instruction: rz(0.7853981633974483) on Physical qubit: Q00. Ignoring."`（`compiler.py:110`）が記録 |

gateway ログ確認:
- `ServerImpl initialized with backend: stim`（13:17:05）
- stim の `counts={'11': 5057, '00': 4943}`（`backend.py:101`）
- クリフォード回路では「Unsupported instruction」警告なし

---

## 6. 復旧と現在の状態

検証後、`default_backend` を元に戻し gateway を再起動（元の挙動を復元）。

- **現在の ent の gateway**: `default_backend: qulacs`（元の挙動）で稼働中。`stim` エントリは registry に残存 → 将来 `default_backend: stim` に変更するだけで即切り替え可能。
- **リポジトリ binding**: `branch:feature/stim-backend`。完全にリリースへ戻す場合は `oqtopus backend install gateway v1.1.16`。
- **変更前 config バックアップ**: `config/gateway/config.yaml.bak_pre_stim`。

---

## 7. 残タスク・未確定事項

- `feature/stim-backend` を develop へマージするか（未実施）。
- ent の gateway をリリース（v1.1.16）へ戻すか、ブランチのままにするか（未実施）。
- シミュレータの `device_id` が "qulacs" のまま（stim でも "qulacs" と表示）。識別したい場合は stim 専用トポロジー（`device_id: "stim"`）を別途用意するオプションあり。
- MP ON 時の `virtual_physical_mapping` は combiner 割当を反映しない既知バグあり（物理割当の確認は combiner ログで行う）。
