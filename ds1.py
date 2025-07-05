# deepseek_country_reports.py

import os
import json
import pandas as pd
import tiktoken
from openai import OpenAI

# ─── DeepSeek Chat client setup ─────────────────────────────────────────────
api_key = os.environ.get("DEEP_SEEK_API") # you have to set this environment variable on your own device or switch to your own API key
if not api_key:
    raise RuntimeError("please set environ DEEP_SEEK_API")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ─── Tokenizer ────────────────────────────────────────────────────────────
# deepseek-reasoner → cl100k_base
try:
    enc = tiktoken.encoding_for_model("deepseek-reasoner")
except KeyError:
    enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

# ─── prompt template in Chinese ───────────────────────────────
SYSTEM_CONTENT = (
    "你是一个擅长做行业分析和生成结构化 JSON 报告的智能助手。"
    "当你收到用户提供的公司列表和描述后，请严格按照以下 JSON 模板来输出，"
    "所有内容都必须用中文撰写：\n\n"
    "```\n"
    "{\n"
    "  \"final_report\": {\n"
    "    \"公司总数\": <总公司数>,\n"
    "    \"1_公司主要业务\": { \"业务类别1\": [<公司A>,<公司B>], ... },\n"
    "    \"2_细分领域覆盖\": { \"上游\": [...], \"中游\": [...], \"下游\": [...] },\n"
    "    \"3_与周边国家的商业往来\": { \"国家1\": {\"提及公司数量\":X, \"公司\":[...]}, ... },\n"
    "    \"4_行业分析\": {\n"
    "       \"行业结构\": \"…\",\n"
    "       \"技术特点\": \"…\",\n"
    "       \"市场分布\": \"…\",\n"
    "       \"发展趋势\": [\"…\",\"…\"],\n"
    "       \"挑战与机遇\": {\"挑战\":[…],\"机遇\":[…]}\n"
    "    },\n"
    "    \"5_重点公司分析\": { \"公司名1\": {\"地位\":\"…\",\"产能\":\"…\"}, … },\n"
    "    \"6_总结\": \"…\"\n"
    "  }\n"
    "}\n"
    "```"
)
SYS_TOKENS = count_tokens(SYSTEM_CONTENT)

# ─── Configs that tested to work ────────────────────────────────────────────────────────────────
MAX_CONTEXT = 65_536   # deepseek-reasoner max input context size
BUFFER      = 1_000     # save completion + safe buffer
MAX_TOKENS  = 15_000    # deepseek-reasoner max output tokens

def main():
    # read the cleaned company profiles CSV and group by country
    df = pd.read_csv("company_profiles_cleaned.csv", encoding="utf-8-sig")
    grouped = df.groupby(["国家（中文）", "国家（英文）"])
    total_countries = len(grouped)

    for idx, ((cn, en), subdf) in enumerate(grouped, start=1):
        print(f"[{idx}/{total_countries}] 处理 {cn} ({en}) 共 {len(subdf)} 条")
        all_reports = {}

        # buffer for this country
        lines_buf = []
        tok_accum  = SYS_TOKENS
        chunk_idx  = 0

        # flush function to send accumulated lines to the API
        def flush_chunk():
            nonlocal lines_buf, tok_accum, chunk_idx

            label      = str(chunk_idx)
            user_block = "\n".join(lines_buf)

            resp = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role":"system", "content": SYSTEM_CONTENT},
                    {"role":"user",   "content":
                        f"国家（中文）：{cn}\n"
                        f"国家（英文）：{en}\n"
                        f"公司总数：{len(subdf)}\n\n"
                        "以下是该国家的公司列表和描述：\n"
                        + user_block
                    }
                ],
                max_tokens=MAX_TOKENS,
                temperature=0.1,
            )

            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                parts = raw.splitlines()
                raw = "\n".join(parts[1:-1])

            try:
                parsed = json.loads(raw).get("final_report", raw)
            except json.JSONDecodeError:
                parsed = raw

            all_reports[label] = parsed
            print(f"  → complete chunk {label} （{len(lines_buf)} 家）")

            # reset for next chunk
            chunk_idx += 1
            lines_buf.clear()
            tok_accum = SYS_TOKENS

        # batch process the companies in this country
        # accumulate lines until we reach the token budget
        for _, row in subdf.iterrows():
            name = row["公司名称"]
            desc = row["description"] if pd.notnull(row["description"]) else "N/A"
            line = f"- {name}: {desc}"
            tks  = count_tokens(line + "\n")

            # if adding this line exceeds the budget, flush current chunk
            if tok_accum + tks + MAX_TOKENS + BUFFER > MAX_CONTEXT:
                flush_chunk()

            lines_buf.append(line)
            tok_accum += tks

        # flush last chunk
        if lines_buf:
            flush_chunk()

        # write out JSON
        fn = en.replace(" ", "_") + ".json"
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(all_reports, f, ensure_ascii=False, indent=2)

        print(f"[{idx}/{total_countries}] Complete → {fn}\n")

if __name__ == "__main__":
    main()
