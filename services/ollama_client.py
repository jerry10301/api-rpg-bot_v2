import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL):
        self.host = host
        self.model = model
        self.api_url = f"{self.host}/api/generate"

    def _generate(self, prompt: str, system_prompt: str = "", format: str = "") -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False
        }
        if format == "json":
            payload["format"] = "json"
            
        try:
            response = requests.post(self.api_url, json=payload, timeout=OLLAMA_TIMEOUT)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.Timeout:
            print(f"\n[Ollama Error] 模型推論超時 ({OLLAMA_TIMEOUT} 秒)。模型可能較大或硬體運算中，請稍候或更改 .env 增加 OLLAMA_TIMEOUT 數值。")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"\n[Ollama Error] 無法連線至模型 ({self.host}): {e}\n請確認 Ollama 已啟動且安裝了 {self.model} 模型。")
            return ""

    def parse_intent(self, user_action: str, available_skills: list) -> dict:
        """
        解析玩家意圖並以 JSON 格式回傳。
        """
        skills_str = ", ".join(available_skills) if available_skills else "無"
        system_prompt = f'''
你是一個精通 TRPG 規則的遊戲主持 (GM)。
根據玩家描述的動作，判斷他想執行的行動類型，並務必以 JSON 格式回傳。
必須包含以下欄位：
- "action_type": 字串 (必須為 "magic", "physical", "defend", "flee", "other" 之一)。請注意：只有「施放明確命名的魔法技能」才視為 "magic"。諸如「拿魔杖敲擊對方」等肉搏行為，無論手中拿的是不是魔法道具，皆屬於 "physical"。
- "skill_used": 如果使用了魔法或特定技能，對應到可用技能清單中的識別碼。若無則填 null。
- "is_valid": 布林值。永遠為 **True**（所有行動均有效，實際判定已由其他系統處理）。
- "required_stat": 需要檢定的屬性字串 ( "STR", "DEX", "CON", "INT", "WIS", "LUK" )。預設物理攻擊為 STR 或 DEX，魔法為 INT 或 WIS，防禦為 CON 或 STR，逃跑為 DEX 或 LUK。
- "difficulty": 該動作的難度等級機率 (10-90 的整數，玩家擲出小於等於此數字才算成功)。
- "reason": 簡短解釋判定原因。

玩家可用技能清單（供判斷 skill_used 時參考）：[{skills_str}]
'''
        result_str = self._generate(user_action, system_prompt=system_prompt, format="json")
        try:
            intent = json.loads(result_str)
            # 強制後處理：所有攻擊行動一律有效，交由傷害計算邏輯決定技能加成
            action_type = intent.get("action_type", "physical")
            if action_type not in ("flee", "defend", "other"):
                intent["is_valid"] = True
            
            # 確保有所需屬性，防呆
            if not intent.get("required_stat"):
                intent["required_stat"] = "STR" if intent.get("action_type") == "physical" else "DEX"
                
            return intent
        except json.JSONDecodeError:
            return {
                "action_type": "physical",
                "skill_used": None,
                "is_valid": True,
                "required_stat": "STR",
                "difficulty": 60,
                "reason": "由於模型未正確回傳 JSON，預設為普通物理判定。"
            }

    def generate_combat_narrative(self, action: str, result_data: dict) -> str:
        """
        生成戰鬥結果敘事，包含玩家攻擊與怪物反擊。
        """
        system_prompt = '''
你是一個奇幻世界 TRPG 遊戲的旁白。
根據玩家的動作與雙方的受傷情況，用生動、有畫面感的一段話描述過程。
請包含以下細節：
1. 玩家的攻擊是否成功。
2. 怪物受到多少傷害，或者如何閃避。
3. 如果怪物沒有死，描述牠如何反擊玩家，以及玩家受到多少傷害。
請使用繁體中文，字數限制在 80-150 字內，敘事節奏緊湊。
'''
        prompt = f"玩家動作：{action}\n戰鬥回合資料：{json.dumps(result_data, ensure_ascii=False)}"
        return self._generate(prompt, system_prompt=system_prompt)

    def generate_quest_narrative(self, quest_name: str, npc_data: dict, result_data: dict) -> str:
        """
        生成任務結果與 NPC 對話敘事。
        """
        npc_name = npc_data.get("name", "NPC")
        npc_title = npc_data.get("title", "")
        npc_personality = npc_data.get("personality", "普通")
        npc_voice = npc_data.get("voice_sample", "")

        system_prompt = f'''
你現在扮演 {npc_title} {npc_name}。
你的個人特質是：{npc_personality}。
你的說話範例參考："{npc_voice}"

【場景：任務回報】
玩家剛剛完成了任務「{quest_name}」並向你回報。
請根據任務結果（獎勵、屬性提升等）提供生動的回饋。
要求：
1. **角色標註**：請將對話內容標註為「{npc_name}：「對話內容」」，並在名字前點綴動作描述。
   例如：{npc_name}點了點頭說：「做得好，這是給你的獎勵。」
2. **互動感**：不要只是單向說話，請包含對玩家動作的觀察或評價（例如點頭、皺眉、拍肩）。
3. **性格一致性**：語氣必須嚴格遵守上述設定（例如教授的冷傲、助教的親切）。
4. **場景描述**：加入環境氛圍或 NPC 的動作細節（如：他放下了手中的試管、她欣慰地笑了笑）。
5. **語言**：使用繁體中文，限制在 100-200 字內。
'''
        prompt = f"任務結算結果資料：{json.dumps(result_data, ensure_ascii=False)}"
        return self._generate(prompt, system_prompt=system_prompt)

    def invent_skill(self, player_name: str, player_action: str, player_level: int, player_stats: dict) -> dict:
        """
        根據玩家的動作描述，讓 LLM 發明一個新技能。
        強制套用平衡代價原則：高傷害必須伴隨高 MP 或低命中修正。
        回傳 dict 或空 dict（若解析失敗）。
        """
        stats_str = ", ".join(f"{k}:{v}" for k, v in player_stats.items())
        system_prompt = f'''
你是一個精通 TRPG 規則的遊戲設計師，負責根據玩家的戰鬥動作，設計一個獨一無二、符合平衡原則的新技能。

**平衡原則（必須嚴格遵守）**：
- 高傷害（damage_multiplier > 2.0）：必須伴隨 mp_cost >= 15 且 accuracy_penalty >= -15
- 中等傷害（damage_multiplier 1.5~2.0）：mp_cost >= 8 且 accuracy_penalty >= -5
- 低傷害（damage_multiplier < 1.5）：可以有較低 MP 消耗，但必須有其他有趣效果

**技能 ID 規則**：
- 使用英文 PascalCase，例如 "ShadowPierce", "FlameWhip", "WindSlash"
- 不能與現有技能重複 (Fireball, Heal, AcidSpit, Thunderbolt, FrostBolt)

**必須以 JSON 格式回傳以下欄位（所有欄位必填）**：
- "skill_id": 英文 PascalCase 技能唯一識別碼
- "name": 技能繁體中文名稱
- "mp_cost": 整數，消耗 MP（1~30）
- "required_stat": "STR", "DEX", "CON", "INT", "WIS", "LUK" 其中之一
- "damage_dice": 骰子表示法，如 "1d6", "2d8"
- "damage_multiplier": 浮點數傷害倍率
- "accuracy_penalty": 整數命中率修正（0 為正常，負數降低命中）
- "element": 元素屬性（"fire","water","wind","earth","thunder","ice","light","dark","none" 其中之一）
- "status_effect": 附帶異常狀態或 null（"燃燒","中毒","麻痺","凍結","混亂" 其中之一）
- "effect_chance": 異常狀態觸發機率（0~50 的整數），無附帶效果填 0
- "description": 技能繁體中文描述，60字以內
'''
        prompt = (
            f"玩家名稱：{player_name}\n"
            f"玩家等級：{player_level}\n"
            f"玩家屬性：{stats_str}\n"
            f"玩家的戰鬥動作：{player_action}\n"
            f"請根據此動作的風格與元素，發明一個符合平衡原則的全新技能。"
        )
        result_str = self._generate(prompt, system_prompt=system_prompt, format="json")
        try:
            skill = json.loads(result_str)
            # 基本防呆驗證
            required_keys = ["skill_id", "name", "mp_cost", "required_stat", "damage_dice", "damage_multiplier", "accuracy_penalty", "description"]
            if all(k in skill for k in required_keys):
                return skill
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def decide_learned_skill(self, player_name: str, player_action: str, player_level: int, player_stats: dict, unlearned_skills: list, all_skills_summary: list = None) -> dict:
        """
        決定玩家學會哪種技能：從現有技能庫挑選，或發明新技能。
        all_skills_summary: 所有技能（含已學）的摘要，供 LLM 感知全域技能狀態。
        """
        skills_info = "\n".join([f"- {s['id']} ({s['name']}): {s['description']}" for s in unlearned_skills])
        # 完整技能庫摘要（含已學技能），讓 LLM 知道所有已存在技能
        all_skills_info = ""
        if all_skills_summary:
            all_skills_info = "\n".join([f"- {s['id']} ({s['name']}): {s['description']}" for s in all_skills_summary])
        stats_str = ", ".join(f"{k}:{v}" for k, v in player_stats.items())

        system_prompt = f'''
你是一個精通 TRPG 的遊戲主持人與平衡設計師。
玩家目前在戰鬥中觸發了「技能領悟」。你的任務是根據「玩家的動作描述」，決定他是學會了一個「現有技能」還是「發明了新技能」。

**世界中所有已存在的技能（包含玩家已學習的）**：
{all_skills_info if all_skills_info else "（尚無已存在技能）"}

**玩家尚未學習的技能清單**：
{skills_info if unlearned_skills else "（目前無現有技能可供學習）"}

**判定準則**：
1. **優先媒合現有技能**：如果玩家的描述與「玩家尚未學習的技能清單」中的某個技能風格、元素高度契合，請讓玩家學會該技能。
2. **發明新技能**：只有在描述非常獨特，且上方「所有已存在技能」清單中沒有任何技能與之相似時，才發明新技能。
3. **嚴格禁止重複**：如果新技能的「繁體中文名稱」與「描述」與上方任何已存在技能高度相似，**絕對不可發明**，必須改為媒合或選擇最接近的現有技能。

**回傳格式 (JSON)**：
- 如果學習「現有技能」，只需回傳：
  {{ "learn_type": "existing", "skill_id": "該技能的 ID" }}
- 如果要「發明新技能」（只有在確認與所有已存在技能不重複時才使用），請回傳：
  {{
    "learn_type": "new",
    "skill_id": "英文唯一識別碼 (PascalCase)",
    "name": "繁體中文名稱",
    "mp_cost": 消耗 MP (1~30),
    "required_stat": "STR/DEX/CON/INT/WIS/LUK",
    "damage_dice": "骰子表示法 (如 1d6)",
    "damage_multiplier": 傷害倍率 (1.0~3.0),
    "accuracy_penalty": 命中修正 (0~-30),
    "element": "元素屬性",
    "status_effect": "狀態名稱或 null",
    "effect_chance": 觸發機率 (0~50),
    "description": "繁體中文描述 (60字內)"
  }}

**平衡限制**：
- 高傷害 (>2.0倍) 必須高 MP 消耗或低命中。
'''
        prompt = (
            f"玩家名稱：{player_name}\n"
            f"玩家等級：{player_level}\n"
            f"玩家屬性：{stats_str}\n"
            f"玩家的戰鬥動作：{player_action}\n"
            f"請根據描述決定學習類型並回傳對應 JSON。"
        )

        result_str = self._generate(prompt, system_prompt=system_prompt, format="json")
        try:
            return json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    def generate_pvp_narrative(
        self,
        p1_name: str,
        p2_name: str,
        battle_log: list,
        winner_name: str | None,
        turns: int,
    ) -> str:
        """
        根據 PvP 自動戰鬥紀錄，生成精彩的決鬥敘事。
        """
        system_prompt = '''\
你是一個奇幻世界 TRPG 遊戲的旁白，負責將系統產生的戰鬥事件紀錄，改寫成如史詩般精彩的決鬥場景描述。
要求：
1. 使用繁體中文。
2. 字數限制在 150-250 字內，敘事緊湊、畫面感強。
3. 包含雙方的攻防過程（命中、閃避、傷害）。
4. 在末尾以一句話宣告勝利者（或平局）。
5. 語氣帶有武俠/奇幻史詩風格。
6. 不需要複述數字資料，而是將其轉換為文學描寫。
'''
        log_text = "\n".join(battle_log)
        prompt = (
            f"決鬥雙方：【{p1_name}】vs 【{p2_name}】\n"
            f"共歷 {turns} 個回合\n"
            f"勝者：{'平局' if winner_name is None else winner_name}\n"
            f"\n--- 戰鬥紀錄 ---\n{log_text}"
        )
        return self._generate(prompt, system_prompt=system_prompt)
