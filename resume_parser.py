"""
AbilityRadar AI — 简历解析模块
==============================

支持从 PDF 文件和图片文件中提取文字，并自动识别结构化字段：
  - 姓名、性别、年龄
  - 学历、专业
  - 技能描述
  - 项目经历
  - 挑战/自我评价

用法：
    python resume_parser.py --file "C:/path/to/resume.pdf"
    python resume_parser.py --file "C:/path/to/resume.jpg"

输出（stdout JSON）：
    {"success": true, "name": "张三", ...}

依赖：
    - pdfminer.six: PDF 文字提取（CJK 支持最好，主力引擎）
    - PyMuPDF (fitz): PDF 文字提取（备选引擎）
    - PaddleOCR: 图片文字识别
"""

import sys
import os
import re
import json

# 确保 stdout 使用 UTF-8 编码（Windows _popen 需要）
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ============================================================
# 第一部分：PDF 文字提取
# ============================================================

def extract_text_from_pdf(pdf_path):
    """
    从 PDF 提取文字，优先使用 pdfminer.six（CJK字体兼容更好），
    失败时回退到 PyMuPDF。
    """
    if not os.path.exists(pdf_path):
        return None, f"文件不存在: {pdf_path}"

    # ── 方法1：pdfminer.six（主力，对中文 CJK 字体 CMap 处理更好）──
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(pdf_path)
        if text and text.strip():
            # 清理 pdfminer 输出中多余的空格和换行
            text = re.sub(r' {3,}', '  ', text)        # 3个以上空格压缩
            text = re.sub(r'\n{4,}', '\n\n\n', text)   # 4个以上换行压缩
            return text.strip(), None
    except ImportError:
        pass  # pdfminer 未安装，尝试下一方法
    except Exception as e:
        pass  # pdfminer 解析失败，继续尝试

    # ── 方法2：PyMuPDF（速度快，但对某些 CJK 字体支持不完整）──
    try:
        import fitz
        doc = fitz.open(pdf_path)
        all_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text('text')
            if text.strip():
                all_text.append(text.strip())
        doc.close()

        if all_text:
            return '\n'.join(all_text), None
        else:
            return None, "PDF 文件中未提取到文字（可能是扫描版图片PDF）"
    except ImportError:
        return None, "请安装 PDF 解析库: pip install pdfminer.six  或  pip install PyMuPDF"
    except Exception as e:
        return None, f"PDF 解析失败: {str(e)}"


# ============================================================
# 第二部分：图片文字识别（OCR）
# ============================================================

def extract_text_from_image(img_path):
    """
    使用 PaddleOCR 从图片中识别文字。
    支持格式: PNG, JPG, JPEG, BMP
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        return None, "PaddleOCR 未安装，请运行: pip install paddleocr paddlepaddle"

    if not os.path.exists(img_path):
        return None, f"文件不存在: {img_path}"

    try:
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='ch',
            use_gpu=False,
            show_log=False,
        )
        result = ocr.ocr(img_path, cls=True)

        if not result or not result[0]:
            return None, "图片中未识别到文字"

        lines = []
        for line_info in result[0]:
            if line_info and len(line_info) >= 2:
                text = line_info[1][0]
                confidence = line_info[1][1]
                if confidence > 0.5:
                    lines.append(text)

        if not lines:
            return None, "图片中未识别到可靠文字"

        return '\n'.join(lines), None
    except Exception as e:
        return None, f"图片 OCR 识别失败: {str(e)}"


# ============================================================
# 第三部分：字段提取
# ============================================================

def extract_name(text):
    """
    提取姓名。
    简历格式多样性大，按优先级尝试多种模式：
    1. "姓名：XXX"
    2. "个人简历"标题后第一行独立的2-3字中文名
    3. 文件开头前几行中的独立短中文行
    """
    # 模式1: "姓名：XXX" / "姓名: XXX"
    m = re.search(r'姓名[：:]\s*([^\s，。,\.\n]{2,4})', text)
    if m:
        return m.group(1).strip()

    # 模式2: "个人简历" / "简历" 标题后的独立短行（即姓名）
    m = re.search(r'(?:个人简历|简历|个人简介)\s*\n+([^\n]{2,4})\s*\n', text)
    if m:
        candidate = m.group(1).strip()
        # 排除不是人名的行（比如日期、数字等）
        if re.match(r'^[一-鿿·]{2,4}$', candidate):
            return candidate

    # 模式3: 前10行中找独立的2-3字纯中文行
    lines = text.split('\n')
    for i, line in enumerate(lines[:10]):
        line = line.strip()
        # 纯中文，2-3个字，不包含常见非名字关键词
        if re.match(r'^[一-鿿·]{2,3}$', line):
            # 排除非姓名关键词
            if line not in ('个人简历', '简历', '个人简介', '教育背景',
                           '项目经历', '工作经历', '自我评价', '求职意向'):
                return line

    return ""


def extract_gender(text):
    """提取性别"""
    # "性别：男/女"
    m = re.search(r'性别[：:]\s*(男|女)', text)
    if m:
        return m.group(1)

    # "政治面貌：中共预备党员" → 无法推断性别
    # 尝试在短句中匹配 "男/女"
    m = re.search(r'(?:本人|我是|性别)[^\n]{0,10}(男|女)', text)
    if m:
        return m.group(1)

    return ""


def extract_age(text):
    """提取年龄"""
    # "年龄：25" / "25岁"
    m = re.search(r'年龄[：:]\s*(\d{1,3})', text)
    if m:
        return m.group(1)
    m = re.search(r'(\d{1,3})\s*岁', text)
    if m:
        return m.group(1)

    # 从出生年月推算: "2004.08" 或 "2004-08" 或 "2004年8月"
    m = re.search(r'(?:出生|出生日期)[：:]\s*(\d{4})', text)
    if m:
        import datetime
        year = int(m.group(1))
        return str(datetime.datetime.now().year - year)

    # 简历中常见的出生年月格式：
    # "2004.08"、"2004-08"、"2004年8月"、"2004/08"
    m = re.search(r'(?:^|\n|\s)(\d{4})[\.\-年/]\d{1,2}(?:[\.\-月/]\d{0,2}|[\s，。,])', text)
    if m:
        import datetime
        year = int(m.group(1))
        if 1960 <= year <= 2010:
            return str(datetime.datetime.now().year - year)
    # 宽松模式：单独的 "2004.08" 格式
    m = re.search(r'(?:^|\n|\s)(\d{4})[\.\-/]\d{1,2}(?:\s|$)', text)
    if m:
        import datetime
        year = int(m.group(1))
        if 1960 <= year <= 2010:
            return str(datetime.datetime.now().year - year)

    return ""


def extract_education(text):
    """提取学历"""
    # "通信工程专业（本科）" → 匹配括号内学历
    m = re.search(r'[（(](博士|硕士|本科|学士|大专|专科)[）)]', text)
    if m:
        return m.group(1)

    # 关键词匹配
    edu_map = [
        ('博士', '博士'), ('硕士', '硕士'), ('研究生', '硕士'),
        ('本科', '本科'), ('学士', '本科'),
        ('大专', '大专'), ('专科', '大专'),
    ]
    for keyword, level in edu_map:
        if keyword in text:
            return level
    return ""


def extract_major(text):
    """提取专业/职业"""
    # "通信工程专业（本科）"
    m = re.search(r'([一-鿿]{2,10})专业[（(]', text)
    if m:
        return m.group(1)

    # "专业：XXX"
    m = re.search(r'专业[：:]\s*([^\n，,。]{2,20})', text)
    if m:
        return m.group(1).strip()

    # "求职意向：嵌入式软件工程师"
    m = re.search(r'求职意向[：:]\s*([^\n，]{2,30})', text)
    if m:
        return m.group(1).strip()

    return ""


# 技能关键词库
TECH_SKILLS = [
    # 编程语言
    'C\\+\\+', 'Python', 'Java', 'JavaScript', 'TypeScript', 'Go', 'Rust',
    'C#', 'PHP', 'Ruby', 'Swift', 'Kotlin', 'MATLAB', 'SQL',
    # 前端
    'React', 'Vue', 'Angular', 'HTML5?', 'CSS3?', 'Node\\.js', 'Webpack',
    '小程序', 'Flutter',
    # 后端
    'Spring', 'Django', 'Flask', 'FastAPI', 'Express', 'Nginx',
    '微服务', '分布式', 'Docker', 'Kubernetes',
    # 数据库
    'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Oracle',
    # AI/ML
    '机器学习', '深度学习', 'NLP', '计算机视觉', 'PyTorch', 'TensorFlow',
    'Transformer', '神经网络', '算法', '图像识别', '人工智能',
    # 嵌入式和硬件
    '嵌入式', '单片机', 'STM32', 'ARM', 'FPGA', 'DSP', 'RTOS',
    'Linux驱动', '通信协议', 'IoT', '传感器',
    # 通信
    '通信原理', '信号处理', '数字信号', '数字电路', '模拟电路', '电路分析',
    # 工具/平台
    'Git', 'Linux', 'AWS', 'Azure', '阿里云', 'DevOps',
    'Jenkins', '敏捷', 'Scrum',
    # 软技能
    '沟通能力', '团队合作', '领导力', '项目管理', '抗压能力',
    # 等级修饰
    '精通', '熟练', '掌握', '熟悉',
]


def extract_skills(text):
    """提取技能描述"""
    found = []
    for skill in TECH_SKILLS:
        if re.search(skill, text, re.IGNORECASE):
            clean = skill.replace('\\+', '+').replace('\\.', '.').replace('?', '')
            if clean not in found:
                found.append(clean)

    if found:
        return '，'.join(found)
    return ""


def extract_section(text, start_markers, end_markers=None):
    """
    从文本中提取两个标记之间的内容块。
    start_markers: 开始的标题列表（如 ["项目经历", "项目经验"]）
    end_markers:   结束的标题列表（如 ["奖项证书", "自我评价"]），
                   为 None 时取到文末
    """
    lines = text.split('\n')

    # 找到起始行
    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        for marker in start_markers:
            if marker in stripped and len(stripped) <= 15:
                start_idx = i
                break
        if start_idx is not None:
            break

    if start_idx is None:
        return ""

    # 找到结束行
    end_idx = len(lines)
    if end_markers:
        for i in range(start_idx + 1, len(lines)):
            stripped = lines[i].strip()
            for marker in end_markers:
                if marker in stripped and len(stripped) <= 15:
                    end_idx = i
                    break
            if end_idx < len(lines):
                break

    # 提取内容（跳过起始标题行，取到结束行之前）
    content_lines = []
    for i in range(start_idx + 1, end_idx):
        line = lines[i].strip()
        if line:
            content_lines.append(line)

    return '\n'.join(content_lines)


def extract_project_experience(text):
    """提取项目经历"""
    # 用章节提取函数
    content = extract_section(
        text,
        start_markers=['项目经历', '项目经验', '项目实践',
                       '工作经历', '工作经验', '实习经历'],
        end_markers=['奖项证书', '荣誉证书', '获奖情况', '技能证书',
                     '教育背景', '自我评价', '个人优势', '语言能力']
    )

    if content and len(content) > 20:
        return content[:2000]

    # 回退：用正则匹配
    patterns = [
        r'(?:项目经历|项目经验|项目实践|工作经历|工作经验|实习经历)[：:]*\s*\n?(.*?)(?:(?:教育背景|学历|技能|证书|荣誉|自我评价|个人优势|奖项|语言能力|$)])',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            result = m.group(1).strip()
            result = re.sub(r'\n{3,}', '\n\n', result)
            if len(result) > 20:
                return result[:2000]

    return ""


def extract_challenge_and_self_eval(text):
    """提取自我评价/挑战经历"""
    # 优先：用章节提取
    content = extract_section(
        text,
        start_markers=['自我评价', '个人优势', '个人特点',
                       '挑战与成长', '成长经历', '个人总结',
                       '社会实践', '校园经历'],
        end_markers=None  # 取到文末
    )

    if not content or len(content) < 5:
        # 回退：取最后一段有意义的文字
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # 从后往前找有实质内容的行
        meaningful = []
        for line in reversed(lines):
            if len(line) > 8 and not re.match(r'^[\d\s\.\-,，。、：:]+$', line):
                meaningful.append(line)
            if len(meaningful) >= 3:
                break
        content = '\n'.join(reversed(meaningful))

    if content:
        return content[:1500]
    return ""


# ============================================================
# 第四部分：综合解析
# ============================================================

def parse_resume_fields(raw_text):
    """
    从简历全文提取所有结构化字段。
    返回 dict。
    """
    result = {
        'name': extract_name(raw_text),
        'gender': extract_gender(raw_text),
        'age': extract_age(raw_text),
        'education': extract_education(raw_text),
        'major': extract_major(raw_text),
        'skills': extract_skills(raw_text),
        'project': extract_project_experience(raw_text),
        'challenge': extract_challenge_and_self_eval(raw_text),
        'raw_text': raw_text,
    }

    # 如果没提取到 project，尝试用"经历"后的内容
    if not result['project'] or len(result['project']) < 10:
        m = re.search(r'(?:经历|大赛)[：:]*\s*\n?(.{50,1000})', raw_text, re.DOTALL)
        if m:
            result['project'] = m.group(1).strip()[:2000]

    # 如果没提取到 challenge，用 skills 和最后一段拼接
    if not result['challenge'] or len(result['challenge']) < 5:
        fallback = result['skills'] if result['skills'] else ''
        if len(fallback) < 20:
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            fallback = '。'.join(lines[-3:]) if len(lines) >= 3 else raw_text[-500:]
        result['challenge'] = fallback[:1500]

    return result


# ============================================================
# 第五部分：命令行入口
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='AbilityRadar AI — 简历解析模块'
    )
    parser.add_argument(
        '--file', type=str, required=True,
        help='简历文件路径（支持 PDF、PNG、JPG、JPEG、BMP）'
    )
    args = parser.parse_args()

    file_path = args.file.strip()
    ext = os.path.splitext(file_path)[1].lower()

    # ── 检查文件存在 ──
    if not os.path.exists(file_path):
        print(json.dumps(
            {'success': False, 'error': f'文件不存在: {file_path}'},
            ensure_ascii=False
        ))
        sys.exit(1)

    # ── 根据扩展名选择解析方式 ──
    raw_text = None
    error = None

    if ext == '.pdf':
        raw_text, error = extract_text_from_pdf(file_path)
    elif ext in ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'):
        raw_text, error = extract_text_from_image(file_path)
    else:
        print(json.dumps({
            'success': False,
            'error': f'不支持的文件格式: {ext}，请使用 PDF、PNG、JPG 格式'
        }, ensure_ascii=False))
        sys.exit(1)

    if error:
        print(json.dumps({'success': False, 'error': error}, ensure_ascii=False))
        sys.exit(1)

    if not raw_text or not raw_text.strip():
        print(json.dumps(
            {'success': False, 'error': '未能从文件中提取到文字内容'},
            ensure_ascii=False
        ))
        sys.exit(1)

    # ── 提取字段 ──
    try:
        fields = parse_resume_fields(raw_text.strip())
        fields['success'] = True
        fields['error'] = ''
    except Exception as e:
        print(json.dumps(
            {'success': False, 'error': f'字段提取失败: {str(e)}'},
            ensure_ascii=False
        ))
        sys.exit(1)

    # ── 输出 JSON 到 stdout ──
    print(json.dumps(fields, ensure_ascii=False))


if __name__ == '__main__':
    main()
