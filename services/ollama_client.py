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
- "action_type": 字串 (必須為 "magic", "physical", "defend", "flee", "other" 之一)。請注意：只有「施放明確在清單中的魔法技能名稱」才視為 "magic"。諸如「拿魔杖敲擊對方」等肉搏行為，無論手中拿的是不是魔法道具，皆屬於 "physical"。
- "skill_used": 如果使用了魔法或特定技能，對應到可用技能清單中的名稱。若無則填 null。
- "is_valid": 布林值。如果是 "magic" 類型，必須確認該技能存在於玩家的可用清單中才算有效 (True)；否則無效 (False)。如果是 "physical", "defend", "flee", "other"，則不論清單，永遠為 True。
- "required_stat": 需要檢定的屬性字串 ( "STR", "DEX", "CON", "INT", "WIS", "LUK" )。預設物理攻擊為 STR 或 DEX，魔法為 INT 或 WIS，防禦為 CON 或 STR，逃跑為 DEX 或 LUK。
- "difficulty": 該動作的難度等級機率 (10-90 的整數，玩家擲出小於等於此數字才算成功)。
- "reason": 簡短解釋判定原因，若無效則說明為何無效。

玩家可用技能清單：[{skills_str}]
'''
        result_str = self._generate(user_action, system_prompt=system_prompt, format="json")
        try:
            intent = json.loads(result_str)
            # 強制後處理：如果不是 magic，一定設為有效，避免 LLM 誤判
            if intent.get("action_type") != "magic":
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
