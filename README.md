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

49 tools across Canvas LMS, Ed Discussion, and Gradescope.

### Canvas — course content (read)
`canvas_list_courses` · `canvas_get_course` · `canvas_list_announcements` · `canvas_list_assignments` · `canvas_get_grades` · `canvas_list_files` · `canvas_get_file_content` · `canvas_list_pages` · `canvas_get_page` · `canvas_list_modules` · `canvas_list_module_items` · `canvas_get_unit_outline_url` · `fetch_unit_outline` (USYD unit outline parser) · `canvas_list_calendar` · `canvas_get_syllabus` · `canvas_download_file`

### Canvas — student dashboard (read)
`canvas_get_todo` · `canvas_get_upcoming` · `canvas_get_missing_submissions` · `canvas_get_submission_status` (per-course, grouped by state) · `canvas_list_discussions` · `canvas_get_discussion` (full threaded view) · `canvas_get_all_grades` (all courses, one call) · `canvas_get_my_submission` (marker feedback + rubric) · `canvas_get_peer_reviews`

### Canvas — write
`canvas_submit_assignment` (text / URL / file upload) · `canvas_post_discussion_entry` (post or reply)

### Ed Discussion — read
`ed_get_user_info` · `ed_list_courses` · `ed_list_threads` · `ed_get_thread` · `ed_search_threads` · `ed_list_lessons` · `ed_get_lesson` (slides + content) · `ed_list_resources` (lecture slides / links / files by category) · `ed_download_resource` (save resource files locally, up to 50MB)

### Ed Discussion — write
`ed_post_thread` · `ed_edit_thread` · `ed_post_comment` (comment or answer) · `ed_reply_to_comment` · `ed_accept_answer` · `ed_thread_action` (star/unstar; staff: pin/lock/endorse)

### Ed Workspaces
`ed_list_workspaces` · `ed_create_workspace` · `ed_update_workspace` (rename / sharing) · `ed_delete_workspace`

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

## Tool Reference

All 49 tools with their input parameters, taken from the Pydantic input models in `canvas_ed_mcp.py` (same grouping as [Features](#features)). Enum types:

- `ResponseFormat`: `markdown` (default) or `json`
- `EnrollmentState`: `active` (default), `completed`, or `all`
- `SubmissionType`: `online_text_entry`, `online_url`, or `online_upload`
- `ThreadFilter`: `all` (default), `unread`, `unanswered`, or `starred`
- `ThreadSort`: `new` (default), `old`, `top`, or `hot`
- `EdThreadType`: `post`, `question` (default), or `announcement`
- `EdCommentType`: `comment` (default) or `answer`
- `EdThreadAction`: `star`, `unstar`, `pin`, `unpin`, `lock`, `unlock`, `endorse`, or `unendorse`

### Canvas — course content (read)

| Tool | Parameters | Description |
| --- | --- | --- |
| `canvas_list_courses` | `enrollment_state` (EnrollmentState, optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get all courses the current user is enrolled in on Canvas. |
| `canvas_get_course` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Get detailed information for a specific Canvas course. |
| `canvas_list_announcements` | `course_id` (str, required); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get announcements for a specific Canvas course. |
| `canvas_list_assignments` | `course_id` (str, required); `include_submissions` (bool, optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get all assignments for a specific Canvas course. |
| `canvas_get_grades` | `course_id` (str, optional); `include_assignment_groups` (bool, optional); `response_format` (ResponseFormat, optional) | Get current user's grades on Canvas. |
| `canvas_list_files` | `course_id` (str, required); `content_types` (List[str], optional); `sort` (str, optional); `search_term` (str, optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get the file list for a Canvas course. |
| `canvas_get_file_content` | `file_id` (str, required); `response_format` (ResponseFormat, optional) | Get file metadata and download URL for a Canvas file. |
| `canvas_list_pages` | `course_id` (str, required); `sort` (str, optional); `search_term` (str, optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get the wiki page list for a Canvas course. |
| `canvas_get_page` | `course_id` (str, required); `page_url_or_id` (str, required); `response_format` (ResponseFormat, optional) | Get the full content of a Canvas wiki page. |
| `canvas_list_modules` | `course_id` (str, required); `include_items` (bool, optional); `search_term` (str, optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get the module list for a Canvas course (weekly/topic structure). |
| `canvas_list_module_items` | `course_id` (str, required); `module_id` (str, required); `include_content_details` (bool, optional); `response_format` (ResponseFormat, optional) | Get items within a specific Canvas module. |
| `canvas_get_unit_outline_url` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Get the Unit Outline URL for a Canvas course (University of Sydney). |
| `fetch_unit_outline` | `unit_outline_url` (str, required); `response_format` (ResponseFormat, optional) | Fetch and parse a University of Sydney Unit Outline page. |
| `canvas_list_calendar` | `context_codes` (List[str], optional); `event_type` (str, optional); `start_date` (str, optional); `end_date` (str, optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get calendar events and assignment due dates from Canvas. |
| `canvas_get_syllabus` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Get the syllabus for a Canvas course. |
| `canvas_download_file` | `file_id` (str, required); `save_path` (str, optional) | Download a Canvas file to the local filesystem. |

### Canvas — student dashboard (read)

| Tool | Parameters | Description |
| --- | --- | --- |
| `canvas_get_todo` | `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get the current user's Canvas to-do list across all courses. |
| `canvas_get_upcoming` | `response_format` (ResponseFormat, optional) | Get the current user's upcoming Canvas events and assignment deadlines. |
| `canvas_get_missing_submissions` | `course_ids` (List[str], optional); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get assignments that are past due and still unsubmitted. |
| `canvas_get_submission_status` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Get per-assignment submission status for a Canvas course. |
| `canvas_list_discussions` | `course_id` (str, required); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Get discussion topics for a Canvas course. |
| `canvas_get_discussion` | `course_id` (str, required); `topic_id` (str, required); `response_format` (ResponseFormat, optional) | Get a Canvas discussion topic with its full threaded replies. |
| `canvas_get_all_grades` | `enrollment_state` (EnrollmentState, optional); `response_format` (ResponseFormat, optional) | Get current grades for ALL your Canvas courses in one call. |
| `canvas_get_my_submission` | `course_id` (str, required); `assignment_id` (str, required); `response_format` (ResponseFormat, optional) | Get your own submission for an assignment, including marker feedback: score, grade, submission comments, and rubric assessment. |
| `canvas_get_peer_reviews` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Get peer reviews assigned TO YOU in a Canvas course. |

### Canvas — write

| Tool | Parameters | Description |
| --- | --- | --- |
| `canvas_submit_assignment` | `course_id` (str, required); `assignment_id` (str, required); `submission_type` (SubmissionType, required); `body` (str, optional); `url` (str, optional); `file_paths` (List[str], optional); `comment` (str, optional) | Submit a Canvas assignment on behalf of the current user. |
| `canvas_post_discussion_entry` | `course_id` (str, required); `topic_id` (str, required); `message` (str, required); `reply_to_entry_id` (str, optional) | Post a new entry (or a reply to an existing entry) in a Canvas discussion. |

### Ed Discussion — read

| Tool | Parameters | Description |
| --- | --- | --- |
| `ed_get_user_info` | `response_format` (ResponseFormat, optional) | Get current Ed Discussion user information. |
| `ed_list_courses` | `year` (str, optional); `session` (str, optional); `response_format` (ResponseFormat, optional) | Get all courses the current user has on Ed Discussion. |
| `ed_list_threads` | `course_id` (int, required); `limit` (int, optional); `filter_type` (ThreadFilter, optional); `category` (str, optional); `sort` (ThreadSort, optional); `offset` (int, optional); `response_format` (ResponseFormat, optional) | Get discussion thread list for a specific Ed course. |
| `ed_get_thread` | `thread_id` (int, required); `response_format` (ResponseFormat, optional) | Get detailed content of a single Ed Discussion thread, including all replies and answers. |
| `ed_search_threads` | `course_id` (int, required); `query` (str, required); `limit` (int, optional); `response_format` (ResponseFormat, optional) | Search threads in an Ed Discussion course. |
| `ed_list_lessons` | `course_id` (int, required); `response_format` (ResponseFormat, optional) | Get the lesson list for an Ed course, grouped by module. |
| `ed_get_lesson` | `lesson_id` (int, required); `include_slide_content` (bool, optional); `response_format` (ResponseFormat, optional) | Get detailed content of a single Ed Lesson, including all slides. |
| `ed_list_resources` | `course_id` (int, required); `response_format` (ResponseFormat, optional) | List the Resources tab of an Ed course (lecture slides, links, files). |
| `ed_download_resource` | `resource_id` (int, required); `save_path` (str, optional) | Download an Ed course resource file (lecture slides, handouts) to the local filesystem. |

### Ed Discussion — write

| Tool | Parameters | Description |
| --- | --- | --- |
| `ed_post_thread` | `course_id` (int, required); `title` (str, required); `content` (str, required); `thread_type` (EdThreadType, optional); `category` (str, required); `subcategory` (str, optional); `is_private` (bool, optional); `is_anonymous` (bool, optional) | Post a new thread to an Ed Discussion course forum. |
| `ed_edit_thread` | `thread_id` (int, required); `title` (str, optional); `content` (str, optional); `category` (str, optional); `subcategory` (str, optional) | Edit an existing Ed Discussion thread (typically your own). |
| `ed_post_comment` | `thread_id` (int, required); `content` (str, required); `comment_type` (EdCommentType, optional); `is_private` (bool, optional); `is_anonymous` (bool, optional) | Post a comment or an answer on an Ed Discussion thread. |
| `ed_reply_to_comment` | `comment_id` (int, required); `content` (str, required); `is_private` (bool, optional); `is_anonymous` (bool, optional) | Reply to an existing comment on an Ed Discussion thread. |
| `ed_accept_answer` | `thread_id` (int, required); `comment_id` (int, required) | Accept an answer on your Ed question thread, marking it resolved. |
| `ed_thread_action` | `thread_id` (int, required); `action` (EdThreadAction, required) | Toggle a state on an Ed thread: star/unstar (student bookmark), pin/unpin, lock/unlock, endorse/unendorse (these six require staff role). |

### Ed Workspaces

| Tool | Parameters | Description |
| --- | --- | --- |
| `ed_list_workspaces` | `course_id` (int, required); `response_format` (ResponseFormat, optional) | List workspaces (cloud IDE instances) of an Ed course. |
| `ed_create_workspace` | `course_id` (int, required); `title` (str, required); `workspace_type` (str, optional) | Create a new workspace (cloud IDE instance) in an Ed course. |
| `ed_update_workspace` | `workspace_id` (str, required); `title` (str, optional); `is_public` (bool, optional); `public_write` (bool, optional) | Update an Ed workspace you own (rename or change sharing). |
| `ed_delete_workspace` | `workspace_id` (str, required) | Permanently delete an Ed workspace you own. |

### Gradescope (read)

| Tool | Parameters | Description |
| --- | --- | --- |
| `gradescope_list_courses` | `response_format` (ResponseFormat, optional) | Get all Gradescope courses for the configured account. |
| `gradescope_list_assignments` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Get all assignments in a Gradescope course with due dates, submission status, and grades. |

### Cross-platform

| Tool | Parameters | Description |
| --- | --- | --- |
| `verify_assessment_coverage` | `course_id` (str, required); `response_format` (ResponseFormat, optional) | Cross-verify assessment coverage between Unit Outline and Canvas assignments. |

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

共 49 个工具，覆盖 Canvas、Ed Discussion、Gradescope 三个平台：

- **Canvas 读取**：课程 / 公告 / 作业 / 成绩（单课明细 + 全部课程一次拉取）/ 文件 / 页面 / 模块 / 日历 / syllabus / USYD unit outline 解析
- **Canvas 学生仪表盘**：待办、即将截止、缺交清单、按提交状态分组、我的提交与批改反馈（评语 + rubric）、peer review、讨论区
- **Canvas 写入**：交作业（文本 / URL / 文件上传）、讨论区发帖回帖
- **Ed 读取**：课程 / 帖子 / 搜索 / Lessons（含 slides）/ Resources（讲义、链接、文件清单，文件可下载到本地）
- **Ed 写入**：发帖、编辑、评论 / 回答、回复、采纳答案、star 收藏（markdown 自动转 Ed XML 格式）
- **Ed Workspaces**：列表、创建、改名 / 共享设置、删除
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
