# Canvas + Ed Discussion MCP Server

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Server-FF6B35?style=flat-square)](https://modelcontextprotocol.io)
[![USYD](https://img.shields.io/badge/USYD-CS-00205B?style=flat-square)](https://www.sydney.edu.au/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

**An MCP server for accessing Canvas LMS and Ed Discussion platforms**

[English](#features) | [中文](#中文)

</div>

---

## Features

### Canvas Features
- **canvas_list_courses** - Get Canvas course list
- **canvas_get_course** - Get course details
- **canvas_list_announcements** - Get course announcements
- **canvas_list_assignments** - Get assignment list

### Ed Discussion Features
- **ed_get_user_info** - Get Ed user information (verify token)
- **ed_list_courses** - Get Ed course list
- **ed_list_threads** - Get discussion thread list
- **ed_get_thread** - Get thread details and replies
- **ed_search_threads** - Search threads

## Installation

### 1. Install Dependencies

```bash
pip install mcp httpx pydantic
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
        "ED_API_TOKEN": "your_Ed_API_Token"
      }
    }
  }
}
```

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
- Valid until: March 18, 2026

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
├── canvas_ed_mcp.py           # Full MCP server (Canvas + Ed)
├── canvas_api_mcp.py          # Canvas-only version
├── requirements.txt           # Python dependencies
├── claude_desktop_config_full.json  # Full configuration example
└── README.md                  # This document
```

## Security Reminder

- **DO NOT** commit API tokens to version control systems
- **DO NOT** share your tokens with others
- Tokens are equivalent to your account password

---

## 中文

### 功能特性

#### Canvas 功能
- **canvas_list_courses** - 获取 Canvas 课程列表
- **canvas_get_course** - 获取课程详情
- **canvas_list_announcements** - 获取课程公告
- **canvas_list_assignments** - 获取作业列表

#### Ed Discussion 功能
- **ed_get_user_info** - 获取 Ed 用户信息（验证令牌）
- **ed_list_courses** - 获取 Ed 课程列表
- **ed_list_threads** - 获取讨论帖列表
- **ed_get_thread** - 获取帖子详情和回复
- **ed_search_threads** - 搜索帖子

### 安装步骤

#### 1. 安装依赖

```bash
pip install mcp httpx pydantic
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
