#!/usr/bin/env python3
"""
Canvas + Ed Discussion MCP Server
University of Sydney Canvas and Ed Discussion Integration

MCP server supporting both Canvas REST API and Ed Discussion API.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict, field_validator

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

# Canvas External Tool tab ID prefix
CANVAS_EXTERNAL_TOOL_TAB_PREFIX = "context_external_tool_"

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


class ThreadSort(str, Enum):
    """Ed Discussion thread sort order"""
    NEW = "new"
    OLD = "old"
    TOP = "top"
    HOT = "hot"


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


class ListModulesInput(BaseModel):
    """Input parameters for getting Canvas course modules"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    include_items: bool = Field(
        default=False,
        description="Whether to inline module items in the response (include[]=items)"
    )
    search_term: Optional[str] = Field(
        default=None,
        description="Search term to filter modules by name"
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of modules to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ListModuleItemsInput(BaseModel):
    """Input parameters for getting items within a Canvas module"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    module_id: str = Field(
        ...,
        description="Canvas module ID",
        min_length=1
    )
    include_content_details: bool = Field(
        default=False,
        description="Whether to include content details like due dates (include[]=content_details)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetGradesInput(BaseModel):
    """Input parameters for getting Canvas grades"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: Optional[str] = Field(
        default=None,
        description="Canvas course ID. If not provided, returns grades for all courses.",
        min_length=1
    )
    include_assignment_groups: bool = Field(
        default=True,
        description="Whether to include assignment group weights (only when course_id is specified)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ListFilesInput(BaseModel):
    """Input parameters for getting Canvas course files"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    content_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by content types (e.g., ['application/pdf', 'image/png'])"
    )
    sort: Optional[str] = Field(
        default=None,
        description="Sort order: 'name', 'size', 'created_at', 'updated_at'"
    )
    search_term: Optional[str] = Field(
        default=None,
        description="Search term to filter files by name"
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of files to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetFileContentInput(BaseModel):
    """Input parameters for getting Canvas file details"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    file_id: str = Field(
        ...,
        description="Canvas file ID",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ListPagesInput(BaseModel):
    """Input parameters for getting Canvas course wiki pages"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    sort: Optional[str] = Field(
        default=None,
        description="Sort order: 'title', 'created_at', 'updated_at'"
    )
    search_term: Optional[str] = Field(
        default=None,
        description="Search term to filter pages by title"
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of pages to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetPageInput(BaseModel):
    """Input parameters for getting a Canvas wiki page"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    page_url_or_id: str = Field(
        ...,
        description="Page URL slug or page ID",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetUnitOutlineUrlInput(BaseModel):
    """Input parameters for getting Canvas Unit Outline URL"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class FetchUnitOutlineInput(BaseModel):
    """Input parameters for fetching and parsing a Unit Outline page"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    unit_outline_url: str = Field(
        ...,
        description="Unit Outline URL from canvas_get_unit_outline_url (e.g., https://sydney.edu.au/units/COMP3221/2026-S1C-ND-CC)",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )

    @field_validator('unit_outline_url')
    @classmethod
    def validate_sydney_domain(cls, v: str) -> str:
        """Restrict URLs to sydney.edu.au to prevent SSRF"""
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if not parsed.hostname or not parsed.hostname.endswith('sydney.edu.au'):
            raise ValueError("URL must be a sydney.edu.au domain")
        return v


class ListCalendarInput(BaseModel):
    """Input parameters for getting Canvas calendar events"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    context_codes: Optional[List[str]] = Field(
        default=None,
        description="Course context codes to filter (e.g., ['course_12345']). If not provided, returns events for all courses."
    )
    event_type: Optional[str] = Field(
        default=None,
        description="Event type filter: 'event' (calendar events) or 'assignment' (assignment due dates)"
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Start date for range filter (ISO 8601 format, e.g., '2026-03-01')"
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date for range filter (ISO 8601 format, e.g., '2026-06-30')"
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of events to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetSyllabusInput(BaseModel):
    """Input parameters for getting Canvas course syllabus"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
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
    category: Optional[str] = Field(
        default=None,
        description="Filter by category (case-sensitive, e.g., 'General', 'Lectures', 'Labs')"
    )
    sort: ThreadSort = Field(
        default=ThreadSort.NEW,
        description="Sort order: 'new' (newest first), 'old' (oldest first), 'top' (most votes), 'hot' (trending)"
    )
    offset: int = Field(
        default=0,
        description="Pagination offset (0-based)",
        ge=0
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
# Input Models - Ed Lessons
# ============================================================================

class EdListLessonsInput(BaseModel):
    """Input parameters for getting Ed Lessons list"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: int = Field(
        ...,
        description="Ed course ID (numeric ID, can be obtained from ed_list_courses)",
        gt=0
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class EdGetLessonInput(BaseModel):
    """Input parameters for getting a single Ed Lesson with slides"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    lesson_id: int = Field(
        ...,
        description="Ed lesson ID (can be obtained from ed_list_lessons)",
        gt=0
    )
    include_slide_content: bool = Field(
        default=True,
        description="Whether to include parsed slide content in the output"
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


async def get_course_name(course_id: str) -> str:
    """Fetch course name from Canvas API with error handling"""
    course = await canvas_api_request(f"/courses/{course_id}")
    if isinstance(course, dict) and "error" not in course:
        return course.get('name', '')
    return ''


# ============================================================================
# Formatting Utilities
# ============================================================================

def format_file_size(size: int) -> str:
    """Format file size in bytes to human-readable string"""
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"

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


def format_modules_markdown(modules: List[Dict], course_name: str = "") -> str:
    """Format Canvas module list as Markdown"""
    if not modules:
        return f"Course {course_name} has no modules." if course_name else "No modules found."

    title = f"# {course_name} - Modules\n" if course_name else "# Course Modules\n"
    lines = [title, f"*Total {len(modules)} modules*\n"]

    for i, module in enumerate(modules, 1):
        name = module.get('name', 'Unnamed Module')
        position = module.get('position', i)
        items_count = module.get('items_count', 0)
        module_id = module.get('id', '')

        lines.append(f"## {position}. {name}")
        lines.append(f"- **Module ID**: {module_id}")
        lines.append(f"- **Items**: {items_count}")

        # Inline items when include_items was used
        items = module.get('items', [])
        if items:
            lines.append("")
            for item in items:
                item_title = item.get('title', 'Untitled')
                item_type = item.get('type', 'Unknown')
                lines.append(f"  - [{item_type}] {item_title}")

        lines.append("")

    return "\n".join(lines)


def format_module_items_markdown(items: List[Dict], module_name: str = "") -> str:
    """Format Canvas module items as Markdown"""
    if not items:
        return f"Module {module_name} has no items." if module_name else "No module items found."

    title = f"# {module_name} - Items\n" if module_name else "# Module Items\n"
    lines = [title, f"*Total {len(items)} items*\n"]

    for i, item in enumerate(items, 1):
        item_title = item.get('title', 'Untitled')
        item_type = item.get('type', 'Unknown')
        item_id = item.get('id', '')
        html_url = item.get('html_url', '')
        external_url = item.get('external_url', '')

        lines.append(f"### {i}. [{item_type}] {item_title}")
        lines.append(f"- **Item ID**: {item_id}")
        if html_url:
            lines.append(f"- **URL**: {html_url}")
        if external_url:
            lines.append(f"- **External URL**: {external_url}")

        # Content details if included
        content_details = item.get('content_details', {})
        if content_details:
            due_at = format_datetime(content_details.get('due_at'))
            if due_at != "Not set":
                lines.append(f"- **Due**: {due_at}")
            points = content_details.get('points_possible')
            if points is not None:
                lines.append(f"- **Points**: {points}")

        lines.append("")

    return "\n".join(lines)


def format_grades_markdown(
    enrollments: List[Dict],
    assignment_groups: Optional[List[Dict]] = None,
    course_name: str = ""
) -> str:
    """Format Canvas grades as Markdown"""
    if not enrollments:
        return "No enrollment/grade data found."

    lines = []
    if course_name:
        lines.append(f"# {course_name} - Grades\n")
    else:
        lines.append("# My Grades\n")

    for enrollment in enrollments:
        grades = enrollment.get('grades', {})
        if not grades:
            continue

        e_course_id = enrollment.get('course_id', '')
        current_score = grades.get('current_score')
        final_score = grades.get('final_score')
        current_grade = grades.get('current_grade')

        if not course_name:
            lines.append(f"## Course ID: {e_course_id}")

        if current_score is not None:
            lines.append(f"- **Current Score**: {current_score}%")
        if current_grade:
            lines.append(f"- **Current Grade**: {current_grade}")
        if final_score is not None:
            lines.append(f"- **Final Score**: {final_score}% *(treats unsubmitted as 0)*")
        lines.append("")

    if assignment_groups:
        lines.append("## Assignment Group Weights\n")
        lines.append("| Group | Weight |")
        lines.append("|-------|--------|")
        for group in assignment_groups:
            name = group.get('name', 'Unknown')
            weight = group.get('group_weight', 0)
            lines.append(f"| {name} | {weight}% |")
        lines.append("")

    return "\n".join(lines)


def format_files_markdown(files: List[Dict], course_name: str = "") -> str:
    """Format Canvas file list as Markdown"""
    if not files:
        return f"Course {course_name} has no files." if course_name else "No files found."

    title = f"# {course_name} - Files\n" if course_name else "# Course Files\n"
    lines = [title, f"*Total {len(files)} files*\n"]

    for i, f in enumerate(files, 1):
        name = f.get('display_name', f.get('filename', 'Unnamed'))
        file_id = f.get('id', '')
        size = f.get('size', 0)
        content_type = f.get('content-type', f.get('content_type', ''))
        created_at = format_datetime(f.get('created_at'))

        size_str = format_file_size(size)

        lines.append(f"### {i}. {name}")
        lines.append(f"- **File ID**: {file_id}")
        lines.append(f"- **Size**: {size_str}")
        if content_type:
            lines.append(f"- **Type**: {content_type}")
        lines.append(f"- **Created**: {created_at}")
        lines.append("")

    return "\n".join(lines)


def format_pages_markdown(pages: List[Dict], course_name: str = "") -> str:
    """Format Canvas wiki page list as Markdown"""
    if not pages:
        return f"Course {course_name} has no pages." if course_name else "No pages found."

    title = f"# {course_name} - Pages\n" if course_name else "# Course Pages\n"
    lines = [title, f"*Total {len(pages)} pages*\n"]

    for i, page in enumerate(pages, 1):
        page_title = page.get('title', 'Untitled')
        page_url = page.get('url', '')
        updated_at = format_datetime(page.get('updated_at'))

        lines.append(f"### {i}. {page_title}")
        lines.append(f"- **Slug**: {page_url}")
        lines.append(f"- **Updated**: {updated_at}")
        lines.append("")

    return "\n".join(lines)


def format_page_detail_markdown(page: Dict) -> str:
    """Format single Canvas wiki page as Markdown"""
    page_title = page.get('title', 'Untitled')
    updated_at = format_datetime(page.get('updated_at'))
    body = strip_html(page.get('body', ''))

    lines = [f"# {page_title}\n"]
    lines.append(f"**Updated**: {updated_at}\n")
    lines.append("---\n")
    lines.append(body if body else "*No content*")

    return "\n".join(lines)


# ============================================================================
# Unit Outline Parser
# ============================================================================

def parse_unit_outline_html(html: str) -> Dict[str, Any]:
    """
    Parse University of Sydney Unit Outline HTML to extract assessment structure.

    Uses BeautifulSoup4 with verified selectors consistent across all faculties.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {
            "error": "BeautifulSoup4 is not installed. Run: pip install beautifulsoup4"
        }

    soup = BeautifulSoup(html, 'html.parser')
    result: Dict[str, Any] = {
        "assessment_structure": [],
        "learning_outcomes": [],
        "course_description": ""
    }

    # Extract assessment structure from #assessment-table
    table = soup.find('table', id='assessment-table')
    if table:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                name = cells[0].get_text(strip=True)
                weight_text = cells[1].get_text(strip=True)
                # Data rows have % in weight and don't start with "Outcomes"
                if '%' in weight_text and not name.startswith('Outcomes'):
                    assessment = {
                        "name": name,
                        "weight": weight_text,
                    }
                    if len(cells) > 2:
                        assessment["due_date"] = cells[2].get_text(strip=True)
                    if len(cells) > 3:
                        assessment["length"] = cells[3].get_text(strip=True)
                    if len(cells) > 4:
                        assessment["ai_policy"] = cells[4].get_text(strip=True)
                    result["assessment_structure"].append(assessment)

    # Extract course description
    desc_el = soup.find('div', class_='course-description')
    if not desc_el:
        desc_el = soup.find('meta', attrs={'name': 'description'})
        if desc_el:
            result["course_description"] = desc_el.get('content', '')
    else:
        result["course_description"] = desc_el.get_text(strip=True)

    # Extract learning outcomes
    outcomes_section = soup.find('div', id='learning-outcomes') or soup.find('div', class_='learning-outcomes')
    if outcomes_section:
        items = outcomes_section.find_all('li')
        result["learning_outcomes"] = [li.get_text(strip=True) for li in items]

    return result


def format_unit_outline_markdown(outline_data: Dict[str, Any]) -> str:
    """Format parsed Unit Outline data as Markdown"""
    lines = ["# Unit Outline\n"]

    if outline_data.get("course_description"):
        lines.append(f"## Course Description\n")
        lines.append(outline_data["course_description"])
        lines.append("")

    assessments = outline_data.get("assessment_structure", [])
    if assessments:
        lines.append("## Assessment Structure\n")
        lines.append("| Assessment | Weight | Due Date | Length | AI Policy |")
        lines.append("|------------|--------|----------|--------|-----------|")
        for a in assessments:
            name = a.get("name", "")
            weight = a.get("weight", "")
            due = a.get("due_date", "")
            length = a.get("length", "")
            ai = a.get("ai_policy", "")
            lines.append(f"| {name} | {weight} | {due} | {length} | {ai} |")
        lines.append("")
    else:
        lines.append("*No assessment structure found.*\n")

    outcomes = outline_data.get("learning_outcomes", [])
    if outcomes:
        lines.append("## Learning Outcomes\n")
        for j, outcome in enumerate(outcomes, 1):
            lines.append(f"{j}. {outcome}")
        lines.append("")

    return "\n".join(lines)


def format_calendar_markdown(events: List[Dict]) -> str:
    """Format Canvas calendar events as Markdown"""
    if not events:
        return "No calendar events found."

    lines = ["# Calendar Events\n", f"*Total {len(events)} events*\n"]

    for i, event in enumerate(events, 1):
        title = event.get('title', 'Untitled Event')
        event_type = event.get('type', 'event')
        start_at = format_datetime(event.get('start_at'))
        end_at = format_datetime(event.get('end_at'))
        description = strip_html(event.get('description', ''))
        context_name = event.get('context_name', '')

        lines.append(f"### {i}. {title}")
        if context_name:
            lines.append(f"- **Course**: {context_name}")
        lines.append(f"- **Type**: {event_type}")
        lines.append(f"- **Start**: {start_at}")
        if end_at != "Not set":
            lines.append(f"- **End**: {end_at}")
        if description:
            if len(description) > 300:
                description = description[:300] + "..."
            lines.append(f"- **Description**: {description}")

        # Assignment-specific fields
        assignment = event.get('assignment', {})
        if assignment:
            points = assignment.get('points_possible')
            if points is not None:
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


def format_ed_lessons_markdown(lessons: List[Dict], modules: List[Dict]) -> str:
    """Format Ed Lessons list as Markdown, grouped by module"""
    if not lessons:
        return "No lessons found."

    # Build module lookup
    module_map: Dict[int, str] = {}
    for m in modules:
        module_map[m.get('id', 0)] = m.get('name', 'Unnamed Module')

    # Group lessons by module_id
    grouped: Dict[int, List[Dict]] = {}
    ungrouped: List[Dict] = []
    for lesson in lessons:
        mid = lesson.get('module_id')
        if mid and mid in module_map:
            grouped.setdefault(mid, []).append(lesson)
        else:
            ungrouped.append(lesson)

    lines = ["# Ed Lessons\n", f"*Total {len(lessons)} lessons*\n"]

    for mid, mod_lessons in grouped.items():
        mod_name = module_map[mid]
        lines.append(f"## {mod_name}\n")
        for lesson in mod_lessons:
            title = lesson.get('title', 'Untitled')
            lesson_id = lesson.get('id', '')
            slide_count = lesson.get('slide_count', 0)
            state = lesson.get('state', '')
            due_at = format_datetime(lesson.get('due_at') or lesson.get('effective_due_at'))

            lines.append(f"- **{title}** (ID: {lesson_id})")
            lines.append(f"  - Slides: {slide_count} | State: {state}")
            if due_at != "Not set":
                lines.append(f"  - Due: {due_at}")
        lines.append("")

    if ungrouped:
        lines.append("## Other Lessons\n")
        for lesson in ungrouped:
            title = lesson.get('title', 'Untitled')
            lesson_id = lesson.get('id', '')
            slide_count = lesson.get('slide_count', 0)
            lines.append(f"- **{title}** (ID: {lesson_id}, Slides: {slide_count})")
        lines.append("")

    return "\n".join(lines)


def format_ed_lesson_detail_markdown(lesson: Dict, include_slides: bool = True) -> str:
    """Format single Ed Lesson detail as Markdown"""
    title = lesson.get('title', 'Untitled')
    lesson_id = lesson.get('id', '')
    slide_count = lesson.get('slide_count', 0)
    state = lesson.get('state', '')
    due_at = format_datetime(lesson.get('due_at') or lesson.get('effective_due_at'))
    created_at = format_datetime(lesson.get('created_at'))

    lines = [f"# {title}\n"]
    lines.append(f"- **Lesson ID**: {lesson_id}")
    lines.append(f"- **Slides**: {slide_count}")
    lines.append(f"- **State**: {state}")
    lines.append(f"- **Due**: {due_at}")
    lines.append(f"- **Created**: {created_at}")

    slides = lesson.get('slides', [])
    if include_slides and slides:
        lines.append(f"\n---\n")
        lines.append(f"## Slides ({len(slides)})\n")
        for slide in slides:
            s_title = slide.get('title', '')
            s_type = slide.get('type', 'document')
            s_index = slide.get('index', 0)
            s_content = slide.get('content', '')

            header = f"### Slide {s_index + 1}"
            if s_title:
                header += f": {s_title}"
            header += f" [{s_type}]"
            lines.append(header)

            if s_content:
                parsed = parse_ed_document(s_content)
                if parsed:
                    lines.append(f"\n{parsed}\n")
                else:
                    lines.append("*Empty slide*\n")
            else:
                lines.append("*No content*\n")
    elif not slides:
        lines.append("\n*No slides available. Use ed_get_lesson to fetch full slide content.*")

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

    course_name = await get_course_name(params.course_id)
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

    course_name = await get_course_name(params.course_id)
    return format_assignments_markdown(result, course_name)


# ============================================================================
# MCP Tools - Canvas Grades, Files, Pages
# ============================================================================

@mcp.tool(
    name="canvas_get_grades",
    annotations={
        "title": "Get Canvas Grades",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_grades(params: GetGradesInput) -> str:
    """
    Get current user's grades on Canvas.

    Returns current_score (based on graded items), final_score (treats unsubmitted as 0),
    and current_grade (letter grade). Optionally includes assignment group weights.

    Args:
        params (GetGradesInput): Input parameters

    Returns:
        str: Grade information (Markdown or JSON format)
    """
    if params.course_id:
        # Grades for a specific course
        enrollment_params: Dict[str, Any] = {
            "user_id": "self",
            "type[]": "StudentEnrollment",
            "include[]": ["grades"]
        }
        enrollments = await canvas_api_request(
            f"/courses/{params.course_id}/enrollments",
            params=enrollment_params
        )
    else:
        # Grades for all courses
        enrollment_params = {
            "type[]": "StudentEnrollment",
            "state[]": "active",
            "include[]": ["grades"],
            "per_page": MAX_PAGE_SIZE
        }
        enrollments = await canvas_api_request(
            "/users/self/enrollments",
            params=enrollment_params
        )

    if isinstance(enrollments, dict) and "error" in enrollments:
        return f"Error: {enrollments['error']}"

    # Get assignment groups and course name in parallel
    assignment_groups = None
    course_name = ""
    if params.course_id:
        if params.include_assignment_groups:
            course_name, groups = await asyncio.gather(
                get_course_name(params.course_id),
                canvas_api_request(f"/courses/{params.course_id}/assignment_groups")
            )
            if isinstance(groups, list):
                assignment_groups = groups
        else:
            course_name = await get_course_name(params.course_id)

    if params.response_format == ResponseFormat.JSON:
        result_data = {"enrollments": enrollments}
        if assignment_groups:
            result_data["assignment_groups"] = assignment_groups
        return json.dumps(result_data, indent=2, ensure_ascii=False)

    return format_grades_markdown(enrollments, assignment_groups, course_name)


@mcp.tool(
    name="canvas_list_files",
    annotations={
        "title": "Get Canvas Course Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_files(params: ListFilesInput) -> str:
    """
    Get the file list for a Canvas course.

    Args:
        params (ListFilesInput): Input parameters

    Returns:
        str: File list (Markdown or JSON format)
    """
    api_params: Dict[str, Any] = {
        "per_page": params.limit
    }

    if params.content_types:
        api_params["content_types[]"] = params.content_types
    if params.sort:
        api_params["sort"] = params.sort
    if params.search_term:
        api_params["search_term"] = params.search_term

    result = await canvas_api_request(f"/courses/{params.course_id}/files", params=api_params)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_files_markdown(result, course_name)


@mcp.tool(
    name="canvas_get_file_content",
    annotations={
        "title": "Get Canvas File Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_file_content(params: GetFileContentInput) -> str:
    """
    Get file metadata and download URL for a Canvas file.

    Returns file details including display name, size, content type, and download URL.
    Does not download the binary content.

    Args:
        params (GetFileContentInput): Input parameters

    Returns:
        str: File details (Markdown or JSON format)
    """
    result = await canvas_api_request(f"/files/{params.file_id}")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    name = result.get('display_name', result.get('filename', 'Unknown'))
    size = result.get('size', 0)
    content_type = result.get('content-type', result.get('content_type', ''))
    url = result.get('url', '')
    created_at = format_datetime(result.get('created_at'))
    updated_at = format_datetime(result.get('updated_at'))

    size_str = format_file_size(size)

    lines = [f"# {name}\n"]
    lines.append(f"- **File ID**: {params.file_id}")
    lines.append(f"- **Size**: {size_str}")
    lines.append(f"- **Type**: {content_type}")
    lines.append(f"- **Created**: {created_at}")
    lines.append(f"- **Updated**: {updated_at}")
    if url:
        lines.append(f"- **Download URL**: {url}")

    return "\n".join(lines)


@mcp.tool(
    name="canvas_list_pages",
    annotations={
        "title": "Get Canvas Course Pages",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_pages(params: ListPagesInput) -> str:
    """
    Get the wiki page list for a Canvas course.

    Args:
        params (ListPagesInput): Input parameters

    Returns:
        str: Page list (Markdown or JSON format)
    """
    api_params: Dict[str, Any] = {
        "per_page": params.limit
    }

    if params.sort:
        api_params["sort"] = params.sort
    if params.search_term:
        api_params["search_term"] = params.search_term

    result = await canvas_api_request(f"/courses/{params.course_id}/pages", params=api_params)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_pages_markdown(result, course_name)


@mcp.tool(
    name="canvas_get_page",
    annotations={
        "title": "Get Canvas Page Content",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_page(params: GetPageInput) -> str:
    """
    Get the full content of a Canvas wiki page.

    Args:
        params (GetPageInput): Input parameters

    Returns:
        str: Page content (Markdown or JSON format)
    """
    result = await canvas_api_request(f"/courses/{params.course_id}/pages/{params.page_url_or_id}")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    return format_page_detail_markdown(result)


# ============================================================================
# MCP Tools - Canvas Modules
# ============================================================================

@mcp.tool(
    name="canvas_list_modules",
    annotations={
        "title": "Get Canvas Course Modules",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_modules(params: ListModulesInput) -> str:
    """
    Get the module list for a Canvas course (weekly/topic structure).

    Modules organize course content into sections (e.g., "Week 1 - Introduction").
    Use include_items=True to also get the items within each module.

    Args:
        params (ListModulesInput): Input parameters

    Returns:
        str: Module list (Markdown or JSON format)
    """
    api_params: Dict[str, Any] = {
        "per_page": params.limit
    }

    if params.include_items:
        api_params["include[]"] = "items"
    if params.search_term:
        api_params["search_term"] = params.search_term

    result = await canvas_api_request(f"/courses/{params.course_id}/modules", params=api_params)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_modules_markdown(result, course_name)


@mcp.tool(
    name="canvas_list_module_items",
    annotations={
        "title": "Get Canvas Module Items",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_module_items(params: ListModuleItemsInput) -> str:
    """
    Get items within a specific Canvas module.

    Returns items like Files, Pages, Assignments, Quizzes, and external links.

    Args:
        params (ListModuleItemsInput): Input parameters

    Returns:
        str: Module items list (Markdown or JSON format)
    """
    api_params: Dict[str, Any] = {}

    if params.include_content_details:
        api_params["include[]"] = "content_details"

    result = await canvas_api_request(
        f"/courses/{params.course_id}/modules/{params.module_id}/items",
        params=api_params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Get module name for display
    module = await canvas_api_request(f"/courses/{params.course_id}/modules/{params.module_id}")
    module_name = module.get('name', '') if isinstance(module, dict) and "error" not in module else ''

    return format_module_items_markdown(result, module_name)


# ============================================================================
# MCP Tools - Canvas Unit Outline
# ============================================================================

@mcp.tool(
    name="canvas_get_unit_outline_url",
    annotations={
        "title": "Get Canvas Unit Outline URL",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_unit_outline_url(params: GetUnitOutlineUrlInput) -> str:
    """
    Get the Unit Outline URL for a Canvas course (University of Sydney).

    Two-step process:
    1. Find the "Unit Outline" tab in course tabs
    2. Extract the sydney.edu.au URL from the external tool configuration

    Args:
        params (GetUnitOutlineUrlInput): Input parameters

    Returns:
        str: Unit Outline URL information (Markdown or JSON format)
    """
    # Step 1: Get course tabs and find Unit Outline
    tabs = await canvas_api_request(f"/courses/{params.course_id}/tabs")

    if isinstance(tabs, dict) and "error" in tabs:
        return f"Error: {tabs['error']}"

    outline_tab = None
    if isinstance(tabs, list):
        for tab in tabs:
            label = tab.get('label', '')
            if 'Unit Outline' in label:
                outline_tab = tab
                break

    if not outline_tab:
        return "Error: No Unit Outline tab found for this course. The course may not have a Unit Outline configured."

    # Step 2: Extract tool_id from tab id (format: "context_external_tool_{tool_id}")
    tab_id = str(outline_tab.get('id', ''))
    tool_id = tab_id.replace(CANVAS_EXTERNAL_TOOL_TAB_PREFIX, '')

    if not tool_id or tool_id == tab_id:
        return f"Error: Could not extract tool ID from tab. Tab ID: {tab_id}"

    # Step 3: Get external tool details for the URL
    tool = await canvas_api_request(f"/courses/{params.course_id}/external_tools/{tool_id}")

    if isinstance(tool, dict) and "error" in tool:
        return f"Error: {tool['error']}"

    custom_fields = tool.get('custom_fields', {})
    unit_outline_url = custom_fields.get('url', '')

    if not unit_outline_url:
        return "Error: Unit Outline URL not found in external tool configuration."

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "unit_outline_url": unit_outline_url,
            "tab_label": outline_tab.get('label', ''),
            "tool_id": tool_id,
            "custom_fields": custom_fields
        }, indent=2, ensure_ascii=False)

    lines = ["# Unit Outline URL\n"]
    lines.append(f"- **Tab**: {outline_tab.get('label', '')}")
    lines.append(f"- **URL**: {unit_outline_url}")
    lines.append(f"\nUse `fetch_unit_outline` with this URL to get the assessment structure.")

    return "\n".join(lines)


@mcp.tool(
    name="fetch_unit_outline",
    annotations={
        "title": "Fetch and Parse Unit Outline",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fetch_unit_outline(params: FetchUnitOutlineInput) -> str:
    """
    Fetch and parse a University of Sydney Unit Outline page.

    Extracts assessment structure (name, weight, due date, length, AI policy),
    learning outcomes, and course description from the HTML page.
    No authentication required.

    Args:
        params (FetchUnitOutlineInput): Input parameters

    Returns:
        str: Parsed Unit Outline data (Markdown or JSON format)
    """
    # Fetch HTML without authentication
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(params.unit_outline_url)
            response.raise_for_status()
            html = response.text
        except httpx.HTTPStatusError as e:
            return f"Error: Failed to fetch Unit Outline (HTTP {e.response.status_code})"
        except httpx.TimeoutException:
            return "Error: Unit Outline request timed out."
        except Exception:
            return "Error: Failed to fetch Unit Outline page."

    # Parse HTML
    outline_data = parse_unit_outline_html(html)

    if "error" in outline_data:
        return f"Error: {outline_data['error']}"

    # Fallback: if no assessment data extracted, return truncated HTML
    if not outline_data.get("assessment_structure"):
        truncated = html[:3000] if len(html) > 3000 else html
        fallback_text = strip_html(truncated)
        return (
            "# Unit Outline (Raw)\n\n"
            "*Could not extract structured assessment data. Showing raw content:*\n\n"
            f"{fallback_text}"
        )

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(outline_data, indent=2, ensure_ascii=False)

    return format_unit_outline_markdown(outline_data)


# ============================================================================
# MCP Tools - Canvas Calendar & Syllabus
# ============================================================================

@mcp.tool(
    name="canvas_list_calendar",
    annotations={
        "title": "Get Canvas Calendar Events",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_calendar(params: ListCalendarInput) -> str:
    """
    Get calendar events and assignment due dates from Canvas.

    Can filter by course, event type, and date range.

    Args:
        params (ListCalendarInput): Input parameters

    Returns:
        str: Calendar events (Markdown or JSON format)
    """
    api_params: Dict[str, Any] = {
        "per_page": params.limit
    }

    if params.context_codes:
        api_params["context_codes[]"] = params.context_codes
    if params.event_type:
        api_params["type"] = params.event_type
    if params.start_date:
        api_params["start_date"] = params.start_date
    if params.end_date:
        api_params["end_date"] = params.end_date

    result = await canvas_api_request("/calendar_events", params=api_params)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    return format_calendar_markdown(result)


@mcp.tool(
    name="canvas_get_syllabus",
    annotations={
        "title": "Get Canvas Course Syllabus",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_syllabus(params: GetSyllabusInput) -> str:
    """
    Get the syllabus for a Canvas course.

    Returns the syllabus body content (HTML converted to plain text).

    Args:
        params (GetSyllabusInput): Input parameters

    Returns:
        str: Syllabus content (Markdown or JSON format)
    """
    api_params: Dict[str, Any] = {
        "include[]": "syllabus_body"
    }

    result = await canvas_api_request(f"/courses/{params.course_id}", params=api_params)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = result.get('name', 'Unknown Course')
    syllabus_body = result.get('syllabus_body', '')

    if not syllabus_body:
        return f"Course {course_name} has no syllabus content."

    syllabus_text = strip_html(syllabus_body)

    lines = [f"# {course_name} - Syllabus\n"]
    lines.append("---\n")
    lines.append(syllabus_text)

    return "\n".join(lines)


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
    Supports sorting by new/old/top/hot, category filtering, and pagination.

    Args:
        params (EdListThreadsInput): Input parameters
            - course_id: Ed course ID (obtained from ed_list_courses)
            - limit: Number to return
            - filter_type: Filter type
            - category: Filter by category (case-sensitive)
            - sort: Sort order (new/old/top/hot)
            - offset: Pagination offset

    Returns:
        str: Thread list
    """
    api_params: Dict[str, Any] = {
        "limit": params.limit,
        "sort": params.sort.value,
        "offset": params.offset
    }

    # Apply filter
    if params.filter_type != ThreadFilter.ALL:
        api_params["filter"] = params.filter_type.value

    # Apply category filter
    if params.category:
        api_params["category"] = params.category

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
# MCP Tools - Ed Lessons
# ============================================================================

@mcp.tool(
    name="ed_list_lessons",
    annotations={
        "title": "Get Ed Lessons List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_list_lessons(params: EdListLessonsInput) -> str:
    """
    Get the lesson list for an Ed course, grouped by module.

    Returns lesson titles, slide counts, due dates, and states.
    Use ed_get_lesson to get full slide content for a specific lesson.

    Args:
        params (EdListLessonsInput): Input parameters

    Returns:
        str: Lesson list (Markdown or JSON format)
    """
    result = await ed_api_request(f"/courses/{params.course_id}/lessons")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    lessons = result.get('lessons', [])
    modules = result.get('modules', [])

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    return format_ed_lessons_markdown(lessons, modules)


@mcp.tool(
    name="ed_get_lesson",
    annotations={
        "title": "Get Ed Lesson Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_get_lesson(params: EdGetLessonInput) -> str:
    """
    Get detailed content of a single Ed Lesson, including all slides.

    Slides contain full content (XML format, automatically parsed to text).
    Slide types: 'document' (text/content) and 'code' (code challenges).

    Args:
        params (EdGetLessonInput): Input parameters

    Returns:
        str: Lesson details with slides (Markdown or JSON format)
    """
    result = await ed_api_request(f"/lessons/{params.lesson_id}")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    lesson = result.get('lesson', result)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(lesson, indent=2, ensure_ascii=False)

    return format_ed_lesson_detail_markdown(lesson, params.include_slide_content)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
