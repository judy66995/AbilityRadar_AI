import sys
sys.stdout.reconfigure(encoding='utf-8')

def mock_onnx_inference(text: str):
    base_score = 5.0
    if "Python" in text or "C++" in text:
        base_score += 1.5
    if "项目" in text or "解决" in text:
        base_score += 1.0
    if "团队" in text or "协作" in text:
        base_score += 0.8
    scores = [
        round(base_score, 1),
        round(base_score+0.3,1),
        round(base_score+0.1,1),
        round(base_score-0.2,1),
        round(base_score-0.5,1),
        round(base_score-0.8,1)
    ]
    return scores

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("0 0 0 0 0 0")
        sys.exit(1)
    user_text = sys.argv[1]
    scores = mock_onnx_inference(user_text)
    # 只输出纯数字，不要任何其他print
    print(" ".join(map(str, scores)))