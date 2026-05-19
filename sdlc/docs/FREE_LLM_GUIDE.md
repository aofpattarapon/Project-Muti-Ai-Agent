# 🆓 Free LLM Guide - ตัวเลือก AI ฟรีและเสียเงิน

---

## 1. Ollama (ฟรี 100% - รันบนเครื่อง)

**ดีที่สุดสำหรับ: DEV Agent, DEVOPS Agent**

```bash
# ติดตั้ง
brew install ollama

# Models ที่แนะนำ
ollama pull hermes3          # ดีสำหรับ instruction following
ollama pull codellama:13b    # ดีสำหรับ coding
ollama pull deepseek-coder:6.7b  # ดีมากสำหรับ code generation
ollama pull llama3.1:8b      # General purpose
ollama pull phi3:mini        # เล็ก เร็ว (RAM น้อยก็รันได้)
```

| Model | RAM ต้องการ | ความสามารถ | เหมาะกับ |
|-------|-----------|-----------|---------|
| hermes3 | 8GB | Instruction following ดี | DEV, DEVOPS |
| codellama:13b | 16GB | Code generation ดีมาก | DEV |
| deepseek-coder:6.7b | 8GB | Code + Debug | DEV |
| llama3.1:8b | 8GB | General | ทุก Role |
| phi3:mini | 4GB | เบา แต่ใช้ได้ | ทดสอบ |

---

## 2. Groq API (ฟรี, ไม่ต้องใส่บัตร)

**ดีที่สุดสำหรับ: ทุก Role เป็น Fallback, เร็วมาก**

```
สมัคร: https://console.groq.com
- ฟรี: Rate limit ~14,400 requests/day (6000 tokens/min)
- ไม่ต้องใส่บัตรเครดิต
```

```python
# ใน .env
GROQ_API_KEY=gsk_xxxxxxxxxxxx
```

**Models ที่ใช้ได้ (ฟรี):**
- `llama-3.1-8b-instant` - เร็วมาก, ดีสำหรับ tasks ทั่วไป
- `llama-3.1-70b-versatile` - ฉลาดกว่า แต่ช้ากว่า
- `mixtral-8x7b-32768` - Context window ใหญ่
- `gemma-7b-it` - Google's model

---

## 3. Claude API (Anthropic)

**ดีที่สุดสำหรับ: CEO, PM, BA, SA, UXUI, QA (Reasoning + Document)**

```
สมัคร: https://console.anthropic.com
Free: $5 credits สำหรับ new accounts
```

```python
# ใน .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

**Models และราคา:**
| Model | ราคา Input | ราคา Output | เหมาะกับ |
|-------|-----------|------------|---------|
| claude-haiku-4-5 | $0.25/1M | $1.25/1M | **ถูกสุด, ใช้เป็น Default** |
| claude-3-5-sonnet | $3/1M | $15/1M | งาน complex |
| claude-opus-4 | $15/1M | $75/1M | งานที่ต้องการ quality สูงสุด |

**แนะนำ:** ใช้ `claude-haiku-4-5` สำหรับ tasks ส่วนใหญ่

---

## 4. Google Gemini API (ฟรี tier)

```
สมัคร: https://makersuite.google.com
Free: 60 requests/minute (Gemini 1.5 Flash)
```

```python
GEMINI_API_KEY=AIzaxxxxxxxxxxxx
```

---

## 5. Together AI (Free $25 credits)

```
สมัคร: https://api.together.xyz
Free: $25 credits สำหรับ new accounts
```

```python
TOGETHER_API_KEY=xxxxxxxxxxxx
```

---

## ตารางสรุป: เลือก LLM อะไรสำหรับงานไหน

| งาน | LLM แนะนำ | ทำไม |
|-----|----------|------|
| วิเคราะห์ Requirements | Claude Haiku | Reasoning ดีมาก |
| เขียน Documents | Claude Haiku | Writing quality สูง |
| เขียน Code | Hermes3/Codellama (Ollama) | ฟรี 100%, Code ดี |
| Infrastructure Scripts | Hermes3 (Ollama) | ฟรี, Shell script ดี |
| QA Test Cases | Claude Haiku | Logic + Testing |
| Quick Tasks | Groq Llama3 | เร็วมาก, ฟรี |

---

## Setup ที่แนะนำสำหรับ Budget ต่างๆ

### 🆓 Budget = ฟรีสมบูรณ์
```
Ollama: hermes3 (DEV, DEVOPS)
Groq: llama3.1-8b (CEO, PM, BA, SA, UXUI, QA)
```

### 💰 Budget = ~$10/เดือน
```
Claude Haiku (CEO, PM, BA, SA, UXUI, QA)
Ollama: hermes3 (DEV, DEVOPS)
```

### 🚀 Budget = ~$50/เดือน
```
Claude Sonnet (CEO, PM, BA, SA)
Claude Haiku (UXUI, QA)
Ollama: codellama:13b (DEV, DEVOPS)
```
