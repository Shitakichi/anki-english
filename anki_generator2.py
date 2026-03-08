import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
import sys

class AnkiCardGenerator:
    def __init__(self, config_path='config.json'):
        """設定ファイルを読み込んで初期化"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.db_path = self.config['database']['path']
        self.ollama_url = self.config['ollama']['base_url']
        self.ollama_model = self.config['ollama']['model']
        self.anki_url = self.config['anki']['connect_url']
        self.deck_name = self.config['anki']['deck_name']
        
        # プロンプト設定を読み込む
        extract_prompt_path = self.config.get('prompts', {}).get('extract_words_prompt', 'prompts/extract_words_prompt.json')
        with open(extract_prompt_path, 'r', encoding='utf-8') as f:
            self.extract_prompt_config = json.load(f)
        
        supplement_prompt_path = self.config.get('prompts', {}).get('supplement_word_prompt', 'prompts/supplement_word_prompt.json')
        with open(supplement_prompt_path, 'r', encoding='utf-8') as f:
            self.supplement_prompt_config = json.load(f)
    
    def read_input_file(self, filepath):
        """入力テキストファイルを読み込む"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content
    
    def extract_words_from_text(self, raw_text):
        """テキストから単語データを抽出(複数対応)"""
        
        prompt_config = self.extract_prompt_config
        
        # プロンプト構築
        prompt_parts = [prompt_config['system_instruction'], "\n\n"]
        
        # 出力形式
        prompt_parts.append("## 出力形式\n")
        prompt_parts.append(json.dumps(prompt_config['output_format']['schema'], ensure_ascii=False, indent=2))
        prompt_parts.append("\n\n")
        
        # ルール
        prompt_parts.append("## ルール\n")
        for rule in prompt_config['rules']:
            prompt_parts.append(f"- {rule}\n")
        prompt_parts.append("\n")
        
        # Few-shot例
        prompt_parts.append("## 例\n\n")
        for i, example in enumerate(prompt_config['examples'], 1):
            prompt_parts.append(f"### 例{i}\n")
            prompt_parts.append(f"入力:\n{example['input']}\n\n")
            prompt_parts.append(f"出力:\n{json.dumps(example['output'], ensure_ascii=False, indent=2)}\n\n")
        
        # 実際の処理対象
        prompt_parts.append("## 実際の処理\n")
        prompt_parts.append(f"入力:\n{raw_text}\n\n")
        prompt_parts.append("出力:\n")
        
        prompt = "".join(prompt_parts)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=90
            )
            response.raise_for_status()
            result = response.json()
            generated_text = result['response'].strip()

            # デバッグ出力を追加
            print("\n🐛 DEBUG: LLMの生の出力:")
            print(generated_text)
            print("-" * 60 + "\n")
            
            # マークダウン除去
            if generated_text.startswith('```json'):
                generated_text = generated_text.replace('```json', '').replace('```', '').strip()
            elif generated_text.startswith('```'):
                generated_text = generated_text.replace('```', '').strip()
            
            # デバッグ出力を追加
            print("\n🐛 DEBUG: マークダウン除去後:")
            print(generated_text)
            print("-" * 60 + "\n")
            
            # JSONパース
            try:
                words_array = json.loads(generated_text)

                # デバッグ出力を追加
                print(f"\n🐛 DEBUG: パース結果の型: {type(words_array)}")
                print(f"🐛 DEBUG: 要素数: {len(words_array) if isinstance(words_array, list) else '配列ではない'}")
                print("-" * 60 + "\n")

                if not isinstance(words_array, list):
                    words_array = [words_array]
                return words_array
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析エラー(抽出): {e}")
                print(f"LLM出力:\n{generated_text}")
                return None
            
        except Exception as e:
            print(f"❌ LLM抽出エラー: {e}")
            return None
    
    def supplement_word_data(self, word_data):
        """単語データに不足情報を補完"""
        
        prompt_config = self.supplement_prompt_config
        
        # プロンプト構築
        prompt_parts = [prompt_config['system_instruction'], "\n\n"]
        
        # TOEIC難易度
        prompt_parts.append("## TOEIC難易度レベル\n")
        for level, desc in prompt_config['toeic_levels'].items():
            prompt_parts.append(f"- {level}: {desc}\n")
        prompt_parts.append("\n")
        
        # 補完ルール
        prompt_parts.append("## 補完ルール\n")
        prompt_parts.append(json.dumps(prompt_config['supplement_rules'], ensure_ascii=False, indent=2))
        prompt_parts.append("\n\n")
        
        # ルール
        prompt_parts.append("## ルール\n")
        for rule in prompt_config['rules']:
            prompt_parts.append(f"- {rule}\n")
        prompt_parts.append("\n")
        
        # Few-shot例
        prompt_parts.append("## 例\n\n")
        for i, example in enumerate(prompt_config['examples'], 1):
            prompt_parts.append(f"### 例{i}\n")
            prompt_parts.append(f"入力:\n{json.dumps(example['input'], ensure_ascii=False, indent=2)}\n\n")
            prompt_parts.append(f"出力:\n{json.dumps(example['output'], ensure_ascii=False, indent=2)}\n\n")
        
        # 実際の処理対象
        prompt_parts.append("## 実際の処理\n")
        prompt_parts.append(f"入力:\n{json.dumps(word_data, ensure_ascii=False, indent=2)}\n\n")
        prompt_parts.append("出力:\n")
        
        prompt = "".join(prompt_parts)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=90
            )
            response.raise_for_status()
            result = response.json()
            generated_text = result['response'].strip()
            
            # マークダウン除去
            if generated_text.startswith('```json'):
                generated_text = generated_text.replace('```json', '').replace('```', '').strip()
            elif generated_text.startswith('```'):
                generated_text = generated_text.replace('```', '').strip()
            
            # JSONパース
            try:
                supplemented_data = json.loads(generated_text)
                return supplemented_data
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析エラー(補完): {e}")
                return word_data  # 失敗時は元データを返す
            
        except Exception as e:
            print(f"❌ 補完処理エラー: {e}")
            return word_data  # 失敗時は元データを返す
    
    def convert_json_to_html(self, data):
        """JSONデータからHTMLコンテンツを生成"""
        html_parts = []
        
        # 単語タイトル
        html_parts.append(f'<div class="word-title">{data["word"]}</div>')
        
        # 品詞セクション
        for pos_section in data.get("pos_sections", []):
            pos = pos_section.get("pos", "")
            meanings = pos_section.get("meanings", [])
            meanings_text = "、".join(meanings)
            
            html_parts.append(f'''<div class="pos-section">
    <span class="pos-label">{pos}</span>
    <span class="pos-meanings">{meanings_text}</span>
</div>''')
        
        # コアイメージ
        core_image = data.get("core_image")
        if core_image:
            html_parts.append(f'''<div class="core-image">
    <div class="core-image-label">コアイメージ</div>
    <div class="core-image-text">{core_image}</div>
</div>''')
        
        # 派生語
        derivatives = data.get("derivatives")
        if derivatives:
            html_parts.append('''<div class="derivatives">
    <div class="derivatives-label">派生語</div>
    <ul class="derivatives-list">''')
            
            for deriv in derivatives:
                word = deriv.get("word", "")
                meaning = deriv.get("meaning", "")
                html_parts.append(f'        <li>{word}({meaning})</li>')
            
            html_parts.append('''    </ul>
</div>''')
        
        # 例文
        examples = data.get("examples")
        if examples:
            html_parts.append('''<div class="examples">
    <div class="examples-label">例文</div>
    <ul class="examples-list">''')
            
            for example in examples:
                html_parts.append(f'        <li>{example}</li>')
            
            html_parts.append('''    </ul>
</div>''')
        
        return "\n".join(html_parts)
    
    def wrap_with_template(self, content_html, for_anki=False):
        """生成されたHTMLをテンプレートに埋め込む
        
        Args:
            content_html: コンテンツHTML
            for_anki: True=Anki用(コンテンツのみ), False=プレビュー用(CSS含む)
        """
        if for_anki:
            # Anki用: コンテンツのみ (Anki側でスタイル適用)
            return content_html
        
        # プレビュー用: CSS含む完全版
        template_path = self.config['templates']['word_template']
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        return template.replace('{{CONTENT}}', content_html)
    
    def save_to_database(self, source_file, raw_input, generated_html, status='pending'):
        """データベースに保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO cards (source_file, category, raw_input, generated_html, deck_name, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (source_file, '単語', raw_input, generated_html, self.deck_name, status))
        
        card_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return card_id
    
    def add_to_anki(self, front_html, card_id):
        """AnkiConnectを使ってAnkiに追加"""
        
        # デッキ作成（存在しない場合）
        deck_payload = {
            "action": "createDeck",
            "version": 6,
            "params": {
                "deck": self.deck_name
            }
        }
        
        try:
            requests.post(self.anki_url, json=deck_payload)
        except:
            pass  # デッキが既に存在する場合はエラーになるが無視
        
        # ノート追加
        model_name = self.config['anki'].get('model_name', 'English Learning Card')
        
        note_payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": self.deck_name,
                    "modelName": model_name,
                    "fields": {
                        "Front": front_html,
                        "Back": ""  # 1面型なのでBackは空
                    },
                    "tags": ["auto-generated", "english-learning"],
                    "options": {
                        "allowDuplicate": False
                    }
                }
            }
        }
        
        try:
            response = requests.post(self.anki_url, json=note_payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                print(f"❌ Anki追加エラー: {result['error']}")
                print(f"   ヒント: Ankiで '{model_name}' ノートタイプが作成されているか確認してください")
                return None
            
            anki_note_id = result.get('result')
            
            # データベース更新
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cards SET anki_note_id = ?, status = 'added'
                WHERE id = ?
            ''', (anki_note_id, card_id))
            conn.commit()
            conn.close()
            
            return anki_note_id
            
        except Exception as e:
            print(f"❌ AnkiConnect通信エラー: {e}")
            return None
    
    def process_file(self, input_filepath):
        """1つのテキストファイルを処理(複数単語対応)"""
        print(f"\n{'='*60}")
        print(f"📄 処理中: {input_filepath}")
        print(f"{'='*60}\n")
        
        # 1. ファイル読み込み
        raw_text = self.read_input_file(input_filepath)
        print(f"✅ 入力テキスト読み込み完了\n")
        print("--- 入力内容 ---")
        print(raw_text)
        print("-" * 60 + "\n")
        
        # 2. 単語抽出(複数対応)
        print("🔍 単語データ抽出中...")
        words_array = self.extract_words_from_text(raw_text)
        
        if not words_array:
            print("❌ 抽出失敗")
            return None
        
        print(f"✅ {len(words_array)}個の単語を抽出しました\n")
        
        # 各単語を処理
        source_filename = Path(input_filepath).name
        processed_count = 0
        
        for idx, word_data in enumerate(words_array, 1):
            print(f"\n{'='*60}")
            print(f"📝 単語 {idx}/{len(words_array)}: {word_data.get('word', '?')}")
            print(f"{'='*60}\n")
            
            print("--- 抽出されたデータ ---")
            print(json.dumps(word_data, ensure_ascii=False, indent=2))
            print("-" * 60 + "\n")
            
            # 3. 補完処理
            print("💡 不足情報の補完中...")
            supplemented_data = self.supplement_word_data(word_data)
            
            print("✅ 補完完了\n")
            print("--- 補完後のデータ ---")
            print(json.dumps(supplemented_data, ensure_ascii=False, indent=2))
            print("-" * 60 + "\n")
            
            # TOEIC難易度表示
            if 'toeic_level' in supplemented_data:
                level_names = {
                    'basic': '基礎(300-500点)',
                    'intermediate': '中級(500-700点)',
                    'advanced': '上級(700-900点)',
                    'expert': '最上級(900点以上)'
                }
                level = supplemented_data['toeic_level']
                print(f"📊 TOEIC難易度: {level_names.get(level, level)}\n")
            
            # 4. HTMLに変換
            print("🔄 HTMLに変換中...")
            content_html = self.convert_json_to_html(supplemented_data)
            print("✅ HTML変換完了\n")
            
            # 5. テンプレート適用
            full_html_preview = self.wrap_with_template(content_html, for_anki=False)
            full_html_anki = self.wrap_with_template(content_html, for_anki=True)
            
            # 6. データベース保存
            card_id = self.save_to_database(source_filename, raw_text, full_html_anki)
            print(f"✅ データベース保存完了 (ID: {card_id})\n")
            
            # 7. プレビュー保存
            preview_path = f"output/preview_{card_id}.html"
            with open(preview_path, 'w', encoding='utf-8') as f:
                f.write(full_html_preview)
            print(f"✅ プレビューファイル保存: {preview_path}\n")
            
            # 8. 確認UI
            print("=" * 60)
            print("📋 確認")
            print("=" * 60)
            print(f"プレビュー: {preview_path} をブラウザで開いて確認してください")
            
            while True:
                choice = input(f"\nAnkiに追加しますか? (y/n/s=スキップして次へ/e=JSON編集/q=終了): ").strip().lower()
                
                if choice == 'e':
                    # JSON編集モード
                    json_path = f"output/edit_{card_id}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(supplemented_data, f, ensure_ascii=False, indent=2)
                    
                    print(f"\n✏️  JSON編集モード")
                    print(f"📄 ファイル: {json_path}")
                    print("📝 エディタで上記ファイルを編集してください")
                    input("\n編集が完了したらEnterキーを押してください...")
                    
                    # 編集後のJSONを読み込み
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            supplemented_data = json.load(f)
                        
                        print("✅ 編集内容を読み込みました\n")
                        print("--- 編集後のデータ ---")
                        print(json.dumps(supplemented_data, ensure_ascii=False, indent=2))
                        print("-" * 60 + "\n")
                        
                        # HTMLを再生成
                        print("🔄 HTMLを再生成中...")
                        content_html = self.convert_json_to_html(supplemented_data)
                        full_html_preview = self.wrap_with_template(content_html, for_anki=False)
                        full_html_anki = self.wrap_with_template(content_html, for_anki=True)
                        
                        # プレビュー更新
                        with open(preview_path, 'w', encoding='utf-8') as f:
                            f.write(full_html_preview)
                        
                        # データベース更新
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE cards SET generated_html = ? WHERE id = ?
                        ''', (full_html_anki, card_id))
                        conn.commit()
                        conn.close()
                        
                        print("✅ プレビューを更新しました")
                        print(f"📄 確認: {preview_path}\n")
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON読み込みエラー: {e}")
                        print("💡 JSONファイルの形式を確認してください")
                        continue
                    except Exception as e:
                        print(f"❌ エラー: {e}")
                        continue
                
                elif choice == 'y':
                    print("\n📤 Ankiに追加中...")
                    anki_id = self.add_to_anki(full_html_anki, card_id)
                    
                    if anki_id:
                        print(f"✅ Anki追加成功! (Note ID: {anki_id})")
                        processed_count += 1
                        break
                    else:
                        print("❌ Anki追加失敗")
                        break
                        
                elif choice == 'n' or choice == 's':
                    print("⏭️  スキップしました")
                    break
                    
                elif choice == 'q':
                    print(f"\n👋 終了します ({processed_count}/{idx}個処理済み)")
                    return processed_count
                    
                else:
                    print("❌ y/n/s/e/q のいずれかを入力してください")
        
        print(f"\n{'='*60}")
        print(f"✅ 全ての単語の処理完了! ({processed_count}/{len(words_array)}個をAnkiに追加)")
        print(f"{'='*60}\n")
        
        return processed_count

def main():
    """メイン処理"""
    print("\n" + "=" * 60)
    print("🎴 Anki英語学習カード自動生成システム - Phase 1.5")
    print("=" * 60 + "\n")
    
    # 引数チェック
    if len(sys.argv) < 2:
        print("使用方法: python anki_generator.py <入力ファイルパス>")
        print("例: python anki_generator.py input/present.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not Path(input_file).exists():
        print(f"❌ ファイルが見つかりません: {input_file}")
        sys.exit(1)
    
    # ジェネレーター初期化
    generator = AnkiCardGenerator()
    
    # 処理実行
    result = generator.process_file(input_file)
    
    if result is not None:
        print("\n" + "=" * 60)
        print("✅ 処理完了!")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("⚠️  処理が完了しましたが、一部エラーがありました")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    main()