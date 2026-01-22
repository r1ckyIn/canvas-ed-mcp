#!/usr/bin/env python3
"""
Canvas + Ed Discussion MCP Server
University of Sydney Canvas and Ed Discussion Integration

MCP server supporting both Canvas REST API and Ed Discussion API.
"""

import json
import os
import re
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# ============================================================================
# Configuration
# ============================================================================

# Canvas API Configuration
CANVAS_BASE_URL = "https://canvas.sydney.edu.au/api/v1"
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN", "")

# Ed Discussion API Configuration
# University of Sydney uses Australia region
ED_BASE_URL = "https://edstem.org/api"
ED_API_TOKEN = os.getenv("ED_API_TOKEN", "")

# HTTP Client Configuration
TIMEOUT_SECONDS = 30
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ============================================================================
# Initialize MCP Server
# ============================================================================

mcp = FastMCP("canvas_ed_mcp")

# ============================================================================
# Enums and Models
# ============================================================================

class ResponseFormat(str, Enum):
    """Output format options"""
    MARKDOWN = "markdown"
    JSON = "json"


class EnrollmentState(str, Enum):
    """Course enrollment state"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ALL = "all"


class ThreadFilter(str, Enum):
    """Ed Discussion thread filter"""
    ALL = "all"
    UNREAD = "unread"
    UNANSWERED = "unanswered"
    STARRED = "starred"


# ============================================================================
# Input Models - Canvas
# ============================================================================

class ListCoursesInput(BaseModel):
    """Input parameters for getting Canvas course list"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    enrollment_state: EnrollmentState = Field(
        default=EnrollmentState.ACTIVE,
        description="Course enrollment state filter: 'active' (current), 'completed' (finished), 'all' (all)"
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Limit on number of results returned",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (human-readable) or 'json' (machine-readable)"
    )


class GetCourseInput(BaseModel):
    """Input parameters for getting single Canvas course details"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    course_id: str = Field(
        ...,
        description="Canvas course ID (e.g., '12345')",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ListAnnouncementsInput(BaseModel):
    """Input parameters for getting Canvas course announcements"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    limit: int = Field(
        default=10,
        description="Number of announcements to return",
        ge=1, le=50
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ListAssignmentsInput(BaseModel):
    """Input parameters for getting Canvas course assignments"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    include_submissions: bool = Field(
        default=False,
        description="Whether to include submission status information"
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of assignments to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# Input Models - Ed Discussion
# ============================================================================

class EdUserInfoInput(BaseModel):
    """Input parameters for getting Ed user information"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class EdListCoursesInput(BaseModel):
    """Input parameters for getting Ed course list"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class EdListThreadsInput(BaseModel):
    """Input parameters for getting Ed Discussion thread list"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    course_id: int = Field(
        ...,
        description="Ed course ID (numeric ID, can be obtained from ed_list_courses)",
        gt=0
    )
    limit: int = Field(
        default=20,
        description="Number of threads to return",
        ge=1, le=100
    )
    filter_type: ThreadFilter = Field(
        default=ThreadFilter.ALL,
        description="Thread filter: 'all', 'unread', 'unanswered', 'starred'"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class EdGetThreadInput(BaseModel):
    """Input parameters for getting single Ed Discussion thread details"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    thread_id: int = Field(
        ...,
        description="Ed thread ID",
        gt=0
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class EdSearchThreadsInput(BaseModel):
    """Input parameters for searching Ed Discussion threads"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    course_id: int = Field(
        ...,
        description="Ed course ID",
        gt=0
    )
    query: str = Field(
        ...,
        description="Search keywords",
        min_length=1
    )
    limit: int = Field(
        default=20,
        description="Number of threads to return",
        ge=1, le=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# API Client Utilities - Canvas
# ============================================================================

def get_canvas_headers() -> Dict[str, str]:
    """Get Canvas API request headers"""
    if not CANVAS_API_TOKEN:
        raise ValueError("Canvas API token not configured. Please set the CANVAS_API_TOKEN environment variable.")
    return {
        "Authorization": f"Bearer {CANVAS_API_TOKEN}",
        "Content-Type": "application/json"
    }


async def canvas_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Any:
    """Send Canvas API request"""
    url = f"{CANVAS_BASE_URL}{endpoint}"
    headers = get_canvas_headers()
    
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            if method == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return _handle_canvas_error(e)
        except httpx.TimeoutException:
            return {"error": "Canvas request timed out. Please try again later."}
        except Exception:
            return {"error": "Canvas request failed. Please try again later."}


def _handle_canvas_error(e: httpx.HTTPStatusError) -> Dict[str, str]:
    """Handle Canvas HTTP errors"""
    status_code = e.response.status_code
    error_messages = {
        401: "Canvas authentication failed. Please check if API token is valid.",
        403: "Canvas permission denied.",
        404: "Canvas resource not found. Please check if the ID is correct.",
        429: "Canvas request rate limit exceeded. Please try again later."
    }
    error_msg = error_messages.get(status_code, f"Canvas API error (status code: {status_code})")
    return {"error": error_msg}


# ============================================================================
# API Client Utilities - Ed Discussion
# ============================================================================

def get_ed_headers() -> Dict[str, str]:
    """Get Ed API request headers"""
    if not ED_API_TOKEN:
        raise ValueError("Ed API token not configured. Please set the ED_API_TOKEN environment variable.")
    return {
        "Authorization": f"Bearer {ED_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


async def ed_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Any:
    """Send Ed Discussion API request"""
    url = f"{ED_BASE_URL}{endpoint}"
    headers = get_ed_headers()
    
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            if method == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return _handle_ed_error(e)
        except httpx.TimeoutException:
            return {"error": "Ed request timed out. Please try again later."}
        except Exception:
            return {"error": "Ed request failed. Please try again later."}


def _handle_ed_error(e: httpx.HTTPStatusError) -> Dict[str, str]:
    """Handle Ed HTTP errors"""
    status_code = e.response.status_code
    error_messages = {
        401: "Ed authentication failed. Please check if API token is valid.",
        403: "Ed permission denied. You may not have access to this course.",
        404: "Ed resource not found. Please check if course ID or thread ID is correct.",
        429: "Ed request rate limit exceeded. Please try again later."
    }
    error_msg = error_messages.get(status_code, f"Ed API error (status code: {status_code})")
    return {"error": error_msg}


# ============================================================================
# Formatting Utilities
# ============================================================================

def format_datetime(dt_string: Optional[str]) -> str:
    """Format datetime string"""
    if not dt_string:
        return "Not set"
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, AttributeError):
        return dt_string


def strip_html(html_content: Optional[str]) -> str:
    """Remove HTML tags"""
    if not html_content:
        return ""
    text = re.sub(r'<[^>]+>', '', html_content)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    return text.strip()


def parse_ed_document(content: str) -> str:
    """Parse Ed Discussion XML document format to plain text"""
    if not content:
        return ""
    # Ed uses special XML format, simple processing
    text = re.sub(r'<[^>]+>', '', content)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    return text.strip()


def format_courses_markdown(courses: List[Dict]) -> str:
    """Format Canvas course list as Markdown"""
    if not courses:
        return "No Canvas courses found."
    
    lines = [f"# My Canvas Courses\n", f"*Total {len(courses)} courses*\n"]
    
    for i, course in enumerate(courses, 1):
        name = course.get('name', 'Unnamed Course')
        code = course.get('course_code', '')
        course_id = course.get('id', '')
        
        lines.append(f"## {i}. {name}")
        if code:
            lines.append(f"- **Course Code**: {code}")
        lines.append(f"- **Course ID**: {course_id}")
        lines.append("")
    
    return "\n".join(lines)


def format_announcements_markdown(announcements: List[Dict], course_name: str = "") -> str:
    """Format Canvas announcement list as Markdown"""
    if not announcements:
        return f"Course {course_name} has no announcements." if course_name else "No announcements."
    
    title = f"# {course_name} - Announcements\n" if course_name else "# Course Announcements\n"
    lines = [title, f"*Total {len(announcements)} announcements*\n"]
    
    for i, ann in enumerate(announcements, 1):
        title = ann.get('title', 'No Title')
        posted_at = format_datetime(ann.get('posted_at'))
        author = ann.get('author', {}).get('display_name', 'Unknown')
        message = strip_html(ann.get('message', ''))
        
        if len(message) > 500:
            message = message[:500] + "..."
        
        lines.append(f"## {i}. {title}")
        lines.append(f"- **Posted by**: {author}")
        lines.append(f"- **Posted at**: {posted_at}")
        lines.append(f"\n{message}\n")
        lines.append("---\n")
    
    return "\n".join(lines)


def format_assignments_markdown(assignments: List[Dict], course_name: str = "") -> str:
    """Format Canvas assignment list as Markdown"""
    if not assignments:
        return f"Course {course_name} has no assignments." if course_name else "No assignments."
    
    title = f"# {course_name} - Assignment List\n" if course_name else "# Assignment List\n"
    lines = [title, f"*Total {len(assignments)} assignments*\n"]
    
    for i, assignment in enumerate(assignments, 1):
        name = assignment.get('name', 'Unnamed Assignment')
        due_at = format_datetime(assignment.get('due_at'))
        points = assignment.get('points_possible', 0)
        assignment_id = assignment.get('id', '')
        
        lines.append(f"## {i}. {name}")
        lines.append(f"- **Assignment ID**: {assignment_id}")
        lines.append(f"- **Due Date**: {due_at}")
        lines.append(f"- **Points**: {points}")
        lines.append("")
    
    return "\n".join(lines)


def format_ed_courses_markdown(courses: List[Dict]) -> str:
    """Format Ed course list as Markdown"""
    if not courses:
        return "No Ed Discussion courses found."
    
    lines = ["# My Ed Discussion Courses\n", f"*Total {len(courses)} courses*\n"]
    
    for i, course in enumerate(courses, 1):
        name = course.get('name', 'Unnamed Course')
        code = course.get('code', '')
        course_id = course.get('id', '')
        year = course.get('year', '')
        session = course.get('session', '')
        
        lines.append(f"## {i}. {name}")
        if code:
            lines.append(f"- **Course Code**: {code}")
        lines.append(f"- **Ed Course ID**: {course_id}")
        if year and session:
            lines.append(f"- **Term**: {year} {session}")
        lines.append("")
    
    return "\n".join(lines)


def format_ed_threads_markdown(threads: List[Dict], course_name: str = "") -> str:
    """Format Ed Discussion thread list as Markdown"""
    if not threads:
        return f"Course {course_name} has no discussion threads." if course_name else "No discussion threads."
    
    title = f"# {course_name} - Ed Discussion Threads\n" if course_name else "# Ed Discussion Threads\n"
    lines = [title, f"*Total {len(threads)} threads*\n"]
    
    for i, thread in enumerate(threads, 1):
        thread_title = thread.get('title', 'No Title')
        thread_id = thread.get('id', '')
        user = thread.get('user', {})
        author = user.get('name', 'Anonymous') if user else 'Anonymous'
        created_at = format_datetime(thread.get('created_at'))
        
        # Thread type and status
        is_question = thread.get('is_question', False)
        is_answered = thread.get('is_answered', False)
        vote_count = thread.get('vote_count', 0)
        reply_count = thread.get('replies_count', 0) or thread.get('num_comments', 0)
        
        thread_type = "Question" if is_question else "Post"
        status = ""
        if is_question:
            status = " ✅ Answered" if is_answered else " ❓ Unanswered"
        
        lines.append(f"## {i}. [{thread_type}] {thread_title}{status}")
        lines.append(f"- **Thread ID**: {thread_id}")
        lines.append(f"- **Author**: {author}")
        lines.append(f"- **Posted at**: {created_at}")
        lines.append(f"- **Replies**: {reply_count} | **Votes**: {vote_count}")
        lines.append("")
    
    return "\n".join(lines)


def format_ed_thread_detail_markdown(thread: Dict) -> str:
    """Format single Ed Discussion thread details as Markdown"""
    thread_title = thread.get('title', 'No Title')
    thread_id = thread.get('id', '')
    user = thread.get('user', {})
    author = user.get('name', 'Anonymous') if user else 'Anonymous'
    created_at = format_datetime(thread.get('created_at'))
    
    # Thread content
    document = thread.get('document', '')
    content = parse_ed_document(document) if document else thread.get('content', '')
    
    is_question = thread.get('is_question', False)
    is_answered = thread.get('is_answered', False)
    
    lines = [f"# {thread_title}\n"]
    
    thread_type = "Question" if is_question else "Post"
    if is_question:
        status = "Answered" if is_answered else "Unanswered"
        lines.append(f"**Type**: {thread_type} ({status})")
    else:
        lines.append(f"**Type**: {thread_type}")
    
    lines.append(f"**Author**: {author}")
    lines.append(f"**Posted at**: {created_at}")
    lines.append(f"**Thread ID**: {thread_id}")
    lines.append(f"\n---\n")
    lines.append(content if content else "*No content*")
    
    # Replies/Answers
    answers = thread.get('answers', [])
    comments = thread.get('comments', [])
    
    if answers:
        lines.append(f"\n## Answers ({len(answers)})\n")
        for j, answer in enumerate(answers, 1):
            ans_user = answer.get('user', {})
            ans_author = ans_user.get('name', 'Anonymous') if ans_user else 'Anonymous'
            ans_time = format_datetime(answer.get('created_at'))
            ans_content = parse_ed_document(answer.get('document', ''))
            is_accepted = answer.get('is_accepted', False)
            
            accepted_mark = " ✅ Accepted Answer" if is_accepted else ""
            lines.append(f"### {j}. {ans_author}{accepted_mark}")
            lines.append(f"*{ans_time}*")
            lines.append(f"\n{ans_content}\n")
    
    if comments:
        lines.append(f"\n## Comments ({len(comments)})\n")
        for j, comment in enumerate(comments, 1):
            cmt_user = comment.get('user', {})
            cmt_author = cmt_user.get('name', 'Anonymous') if cmt_user else 'Anonymous'
            cmt_time = format_datetime(comment.get('created_at'))
            cmt_content = parse_ed_document(comment.get('document', ''))
            
            lines.append(f"### {j}. {cmt_author}")
            lines.append(f"*{cmt_time}*")
            lines.append(f"\n{cmt_content}\n")
    
    if not answers and not comments:
        lines.append("\n*No replies yet*")
    
    return "\n".join(lines)


# ============================================================================
# MCP Tools - Canvas
# ============================================================================

@mcp.tool(
    name="canvas_list_courses",
    annotations={
        "title": "Get Canvas Course List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_courses(params: ListCoursesInput) -> str:
    """
    Get all courses the current user is enrolled in on Canvas.
    
    Returns course name, course code, course ID, and other basic information.
    
    Args:
        params (ListCoursesInput): Input parameters
    
    Returns:
        str: Course list (Markdown or JSON format)
    """
    api_params = {
        "enrollment_state": params.enrollment_state.value,
        "per_page": params.limit,
        "include[]": ["term"]
    }
    
    result = await canvas_api_request("/courses", params=api_params)
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    return format_courses_markdown(result)


@mcp.tool(
    name="canvas_get_course",
    annotations={
        "title": "Get Canvas Course Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_course(params: GetCourseInput) -> str:
    """
    Get detailed information for a specific Canvas course.
    
    Args:
        params (GetCourseInput): Input parameters
    
    Returns:
        str: Course details
    """
    api_params = {
        "include[]": ["term", "teachers", "total_students", "syllabus_body"]
    }
    
    result = await canvas_api_request(f"/courses/{params.course_id}", params=api_params)
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    lines = [f"# {result.get('name', 'Unnamed Course')}\n"]
    if result.get('course_code'):
        lines.append(f"**Course Code**: {result['course_code']}")
    lines.append(f"**Course ID**: {result.get('id', '')}")
    if result.get('teachers'):
        teacher_names = [t.get('display_name', '') for t in result['teachers']]
        lines.append(f"**Teachers**: {', '.join(teacher_names)}")
    if result.get('syllabus_body'):
        lines.append(f"\n## Syllabus\n{strip_html(result['syllabus_body'])}")
    
    return "\n".join(lines)


@mcp.tool(
    name="canvas_list_announcements",
    annotations={
        "title": "Get Canvas Course Announcements",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_announcements(params: ListAnnouncementsInput) -> str:
    """
    Get announcements for a specific Canvas course.
    
    Args:
        params (ListAnnouncementsInput): Input parameters
    
    Returns:
        str: Announcement list
    """
    api_params = {
        "context_codes[]": [f"course_{params.course_id}"],
        "per_page": params.limit
    }
    
    result = await canvas_api_request("/announcements", params=api_params)
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    course = await canvas_api_request(f"/courses/{params.course_id}")
    course_name = course.get('name', '') if isinstance(course, dict) else ''
    
    return format_announcements_markdown(result, course_name)


@mcp.tool(
    name="canvas_list_assignments",
    annotations={
        "title": "Get Canvas Course Assignments",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_assignments(params: ListAssignmentsInput) -> str:
    """
    Get all assignments for a specific Canvas course.
    
    Args:
        params (ListAssignmentsInput): Input parameters
    
    Returns:
        str: Assignment list
    """
    api_params = {
        "per_page": params.limit,
        "order_by": "due_at"
    }
    
    if params.include_submissions:
        api_params["include[]"] = ["submission"]
    
    result = await canvas_api_request(f"/courses/{params.course_id}/assignments", params=api_params)
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    course = await canvas_api_request(f"/courses/{params.course_id}")
    course_name = course.get('name', '') if isinstance(course, dict) else ''
    
    return format_assignments_markdown(result, course_name)


# ============================================================================
# MCP Tools - Ed Discussion
# ============================================================================

@mcp.tool(
    name="ed_get_user_info",
    annotations={
        "title": "Get Ed User Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_get_user_info(params: EdUserInfoInput) -> str:
    """
    Get current Ed Discussion user information.
    
    Used to verify if API token is valid and get basic user information.
    
    Args:
        params (EdUserInfoInput): Input parameters
    
    Returns:
        str: User information
    """
    result = await ed_api_request("/user")
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    user = result.get('user', result)
    
    lines = ["# Ed Discussion User Information\n"]
    lines.append(f"**Name**: {user.get('name', 'Unknown')}")
    lines.append(f"**Email**: {user.get('email', 'Unknown')}")
    lines.append(f"**User ID**: {user.get('id', '')}")
    
    return "\n".join(lines)


@mcp.tool(
    name="ed_list_courses",
    annotations={
        "title": "Get Ed Discussion Course List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_list_courses(params: EdListCoursesInput) -> str:
    """
    Get all courses the current user has on Ed Discussion.
    
    Returns course name, course code, and Ed course ID.
    Use Ed course ID to get discussion threads for that course.
    
    Args:
        params (EdListCoursesInput): Input parameters
    
    Returns:
        str: Ed course list
    """
    result = await ed_api_request("/user")
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    courses = result.get('courses', [])
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(courses, indent=2, ensure_ascii=False)
    
    return format_ed_courses_markdown(courses)


@mcp.tool(
    name="ed_list_threads",
    annotations={
        "title": "Get Ed Discussion Thread List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_list_threads(params: EdListThreadsInput) -> str:
    """
    Get discussion thread list for a specific Ed course.
    
    Can filter for unread, unanswered, or starred threads.
    
    Args:
        params (EdListThreadsInput): Input parameters
            - course_id: Ed course ID (obtained from ed_list_courses)
            - limit: Number to return
            - filter_type: Filter type
    
    Returns:
        str: Thread list
    """
    api_params = {
        "limit": params.limit,
        "sort": "new"
    }
    
    # Apply filter
    if params.filter_type == ThreadFilter.UNREAD:
        api_params["filter"] = "unread"
    elif params.filter_type == ThreadFilter.UNANSWERED:
        api_params["filter"] = "unanswered"
    elif params.filter_type == ThreadFilter.STARRED:
        api_params["filter"] = "starred"
    
    result = await ed_api_request(f"/courses/{params.course_id}/threads", params=api_params)
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    threads = result.get('threads', result) if isinstance(result, dict) else result
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(threads, indent=2, ensure_ascii=False)
    
    return format_ed_threads_markdown(threads if isinstance(threads, list) else [])


@mcp.tool(
    name="ed_get_thread",
    annotations={
        "title": "Get Ed Discussion Thread Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_get_thread(params: EdGetThreadInput) -> str:
    """
    Get detailed content of a single Ed Discussion thread, including all replies and answers.
    
    Args:
        params (EdGetThreadInput): Input parameters
            - thread_id: Thread ID
    
    Returns:
        str: Thread details and replies
    """
    result = await ed_api_request(f"/threads/{params.thread_id}")
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    thread = result.get('thread', result) if isinstance(result, dict) else result
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(thread, indent=2, ensure_ascii=False)
    
    return format_ed_thread_detail_markdown(thread)


@mcp.tool(
    name="ed_search_threads",
    annotations={
        "title": "Search Ed Discussion Threads",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_search_threads(params: EdSearchThreadsInput) -> str:
    """
    Search threads in an Ed Discussion course.
    
    Args:
        params (EdSearchThreadsInput): Input parameters
            - course_id: Ed course ID
            - query: Search keywords
            - limit: Number to return
    
    Returns:
        str: Search results
    """
    api_params = {
        "limit": params.limit,
        "search": params.query
    }
    
    result = await ed_api_request(f"/courses/{params.course_id}/threads", params=api_params)
    
    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"
    
    threads = result.get('threads', result) if isinstance(result, dict) else result
    
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(threads, indent=2, ensure_ascii=False)
    
    if not threads:
        return f"No threads found containing '{params.query}'."
    
    lines = [f"# Search Results: '{params.query}'\n"]
    lines.append(format_ed_threads_markdown(threads if isinstance(threads, list) else []))
    
    return "\n".join(lines)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
