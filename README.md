<div align="center">

# Canvas + Ed Discussion MCP Server

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Server-FF6B35?style=flat-square)](https://modelcontextprotocol.io)
[![USYD](https://img.shields.io/badge/USYD-CS-00205B?style=flat-square)](https://www.sydney.edu.au/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

**An MCP server for accessing Canvas LMS and Ed Discussion platforms**

[English](#features) | [中文](#中文)

</div>

---

## Features

43 tools across Canvas LMS, Ed Discussion, and Gradescope.

### Canvas — course content (read)
`canvas_list_courses` · `canvas_get_course` · `canvas_list_announcements` · `canvas_list_assignments` · `canvas_get_grades` · `canvas_get_all_grades` (all courses, one call) · `canvas_list_files` · `canvas_get_file_content` · `canvas_download_file` · `canvas_list_pages` · `canvas_get_page` · `canvas_list_modules` · `canvas_list_module_items` · `canvas_list_calendar` · `canvas_get_syllabus` · `canvas_get_unit_outline_url` · `fetch_unit_outline` (USYD unit outline parser)

### Canvas — student dashboard (read)
`canvas_get_todo` · `canvas_get_upcoming` · `canvas_get_missing_submissions` · `canvas_get_submission_status` (per-course, grouped by state) · `canvas_get_my_submission` (marker feedback + rubric) · `canvas_get_peer_reviews` · `canvas_list_discussions` · `canvas_get_discussion` (full threaded view)

### Canvas — write
`canvas_submit_assignment` (text / URL / file upload) · `canvas_post_discussion_entry` (post or reply)

### Ed Discussion — read
`ed_get_user_info` · `ed_list_courses` · `ed_list_threads` · `ed_get_thread` · `ed_search_threads` · `ed_list_lessons` · `ed_get_lesson` (slides + content)

### Ed Discussion — write
`ed_post_thread` · `ed_edit_thread` · `ed_post_comment` (comment or answer) · `ed_reply_to_comment` · `ed_accept_answer` · `ed_thread_action` (star/unstar; staff: pin/lock/endorse)

Write content is markdown — automatically converted to Ed's XML document format (headings, bold/italic, code spans/blocks, lists, links, math, callouts).

### Gradescope (read)
`gradescope_list_courses` · `gradescope_list_assignments` (due dates, submission status, grades)

### Cross-platform
`verify_assessment_coverage` (Unit Outline vs Canvas assignments)

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Claude Desktop

Edit the Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following configuration:

```json
{
  "mcpServers": {
    "canvas-ed-mcp": {
      "command": "python",
      "args": [
        "/your/full/path/canvas_ed_mcp.py"
      ],
      "env": {
        "CANVAS_API_TOKEN": "your_Canvas_API_Token",
        "ED_API_TOKEN": "your_Ed_API_Token",
        "GRADESCOPE_EMAIL": "your_email (optional, for Gradescope tools)",
        "GRADESCOPE_PASSWORD": "your_password (optional)"
      }
    }
  }
}
```

> Gradescope has no official API — tools use the maintained
> [gradescopeapi](https://pypi.org/project/gradescopeapi/) scraping library.
> University SSO accounts must first set a native Gradescope password via
> the "forgot password" flow on gradescope.com.

### 3. Restart Claude Desktop

## Usage Examples

### Canvas Operations

```
List all my Canvas courses
```

```
Get announcements for course ID 12345
```

```
View my assignment list
```

### Ed Discussion Operations

```
List my Ed Discussion courses
```

```
Get the latest discussion threads for Ed course ID 12345
```

```
Search for threads about "assignment" in Ed course
```

```
Get detailed content and replies for Ed thread ID 67890
```

## API Token Information

### Canvas API Token
- Source: Canvas → Account → Settings → Approved Integrations → + New Access Token

### Ed Discussion API Token
- Source: Ed Discussion → Settings → API
- Note: Ed API is an unofficial beta version, endpoints may change

## Workflow Examples

### View All Course Discussions

1. First get Ed course list: `ed_list_courses`
2. Note the Ed course ID of the course you're interested in
3. Get threads for that course: `ed_list_threads` (using course ID)
4. View specific thread details: `ed_get_thread` (using thread ID)

### Check Assignment Due Dates

1. Get Canvas course list: `canvas_list_courses`
2. Get course assignments: `canvas_list_assignments` (using Canvas course ID)

## Troubleshooting

### Ed API Errors

**401 Authentication Failed**
- Check if Ed API token is correct
- Confirm token hasn't expired

**404 Resource Not Found**
- Ed course ID and Canvas course ID are different
- Use `ed_list_courses` to get the correct Ed course ID

### Canvas API Errors

**404 Resource Not Found**
- Check if Canvas course ID is correct
- Confirm you have permission to access the course

## Technical Notes

### Ed API Endpoints

Ed Discussion API is unofficial and based on reverse engineering. Main endpoints:

- `GET /api/user` - Get user information and course list
- `GET /api/courses/{id}/threads` - Get course threads
- `GET /api/threads/{id}` - Get thread details

### Data Format

Ed Discussion uses a special XML format to store thread content. The MCP server automatically parses this into plain text.

## Project Structure

```
canvas-ed-mcp/
├── canvas_ed_mcp.py           # Full MCP server (Canvas + Ed + Gradescope)
├── requirements.txt           # Python dependencies
├── claude_desktop_config_example.json  # Configuration example
└── README.md                  # This document
```

## Security Reminder

- **DO NOT** commit API tokens to version control systems
- **DO NOT** share your tokens with others
- Tokens are equivalent to your account password

---

## 中文

### 功能特性

共 43 个工具，覆盖 Canvas、Ed Discussion、Gradescope 三个平台：

- **Canvas 读取**：课程 / 公告 / 作业 / 成绩（单课明细 + 全部课程一次拉取）/ 文件 / 页面 / 模块 / 日历 / syllabus / USYD unit outline 解析
- **Canvas 学生仪表盘**：待办、即将截止、缺交清单、按提交状态分组、我的提交与批改反馈（评语 + rubric）、peer review、讨论区
- **Canvas 写入**：交作业（文本 / URL / 文件上传）、讨论区发帖回帖
- **Ed 读取**：课程 / 帖子 / 搜索 / Lessons（含 slides）
- **Ed 写入**：发帖、编辑、评论 / 回答、回复、采纳答案、star 收藏（markdown 自动转 Ed XML 格式）
- **Gradescope 读取**：课程、作业（截止时间 / 提交状态 / 分数）
- **跨平台**：Unit Outline 与 Canvas 作业对账

### 安装步骤

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置 Claude Desktop

编辑 Claude Desktop 配置文件：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### 3. 重启 Claude Desktop

### 安全提醒

- **不要** 将 API 令牌提交到版本控制系统
- **不要** 与他人分享你的令牌
- 令牌相当于你的账户密码

---

## License

For educational purposes only. Ed API is an unofficial beta version, use at your own risk.

---

## Author

**Ricky** - CS Student @ University of Sydney

[![GitHub](https://img.shields.io/badge/GitHub-r1ckyIn-181717?style=flat-square&logo=github)](https://github.com/r1ckyIn)

Interested in Cloud Engineering & DevOps
