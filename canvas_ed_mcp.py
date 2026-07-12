#!/usr/bin/env python3
"""
Canvas + Ed Discussion MCP Server
University of Sydney Canvas and Ed Discussion Integration

MCP server supporting both Canvas REST API and Ed Discussion API.
"""

import asyncio
import dataclasses
import json
import mimetypes
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

# Gradescope Configuration (no official API; gradescopeapi scrapes the site.
# SSO accounts must set a native password via Gradescope's "forgot password")
GRADESCOPE_EMAIL = os.getenv("GRADESCOPE_EMAIL", "")
GRADESCOPE_PASSWORD = os.getenv("GRADESCOPE_PASSWORD", "")

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


class SubmissionType(str, Enum):
    """Canvas assignment submission type"""
    TEXT = "online_text_entry"
    URL = "online_url"
    UPLOAD = "online_upload"


class EdThreadType(str, Enum):
    """Ed Discussion thread type"""
    POST = "post"
    QUESTION = "question"
    ANNOUNCEMENT = "announcement"


class EdCommentType(str, Enum):
    """Ed Discussion comment type"""
    COMMENT = "comment"
    ANSWER = "answer"


class EdThreadAction(str, Enum):
    """Ed Discussion thread toggle action"""
    STAR = "star"
    UNSTAR = "unstar"
    PIN = "pin"
    UNPIN = "unpin"
    LOCK = "lock"
    UNLOCK = "unlock"
    ENDORSE = "endorse"
    UNENDORSE = "unendorse"


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


class DownloadFileInput(BaseModel):
    """Input parameters for downloading a Canvas file"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    file_id: str = Field(
        ...,
        description="Canvas file ID to download",
        min_length=1
    )
    save_path: Optional[str] = Field(
        default=None,
        description="Full file path to save. Defaults to current directory + Canvas display_name"
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
# Input Models - Canvas Student Dashboard
# ============================================================================

class GetTodoInput(BaseModel):
    """Input parameters for getting the current user's Canvas to-do list"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of to-do items to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetUpcomingInput(BaseModel):
    """Input parameters for getting the current user's upcoming Canvas events"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetMissingSubmissionsInput(BaseModel):
    """Input parameters for getting the current user's missing (past-due, unsubmitted) assignments"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_ids: Optional[List[str]] = Field(
        default=None,
        description="Canvas course IDs to filter (e.g., ['69855']). If not provided, checks all courses."
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


class GetSubmissionStatusInput(BaseModel):
    """Input parameters for getting per-assignment submission status in a Canvas course"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID (e.g., '69855')",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class ListDiscussionsInput(BaseModel):
    """Input parameters for getting Canvas course discussion topics"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        description="Number of discussion topics to return",
        ge=1, le=MAX_PAGE_SIZE
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetDiscussionInput(BaseModel):
    """Input parameters for getting a Canvas discussion topic with all entries"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    topic_id: str = Field(
        ...,
        description="Discussion topic ID (obtained from canvas_list_discussions)",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetAllGradesInput(BaseModel):
    """Input parameters for getting grades across all Canvas courses in one call"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    enrollment_state: EnrollmentState = Field(
        default=EnrollmentState.ACTIVE,
        description="Course enrollment state filter: 'active', 'completed', or 'all'"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetMySubmissionInput(BaseModel):
    """Input parameters for getting your own submission with feedback for an assignment"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    assignment_id: str = Field(
        ...,
        description="Canvas assignment ID",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetPeerReviewsInput(BaseModel):
    """Input parameters for getting your assigned peer reviews in a course"""
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
# Input Models - Canvas Write Operations
# ============================================================================

class SubmitAssignmentInput(BaseModel):
    """Input parameters for submitting a Canvas assignment"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    assignment_id: str = Field(
        ...,
        description="Canvas assignment ID (obtained from canvas_list_assignments)",
        min_length=1
    )
    submission_type: SubmissionType = Field(
        ...,
        description=(
            "Submission type: 'online_text_entry' (text body), "
            "'online_url' (a URL), or 'online_upload' (local files)"
        )
    )
    body: Optional[str] = Field(
        default=None,
        description="Text content for online_text_entry submissions (HTML allowed)"
    )
    url: Optional[str] = Field(
        default=None,
        description="URL for online_url submissions"
    )
    file_paths: Optional[List[str]] = Field(
        default=None,
        description="Absolute local file paths for online_upload submissions"
    )
    comment: Optional[str] = Field(
        default=None,
        description="Optional submission comment visible to markers"
    )


class PostDiscussionEntryInput(BaseModel):
    """Input parameters for posting to a Canvas discussion"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID",
        min_length=1
    )
    topic_id: str = Field(
        ...,
        description="Discussion topic ID (obtained from canvas_list_discussions)",
        min_length=1
    )
    message: str = Field(
        ...,
        description="Message content (HTML allowed)",
        min_length=1
    )
    reply_to_entry_id: Optional[str] = Field(
        default=None,
        description="Entry ID to reply to. If omitted, posts a new top-level entry."
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

    year: Optional[str] = Field(
        default=None,
        description="Filter by year (e.g., '2026'). Filters out courses from other years."
    )
    session: Optional[str] = Field(
        default=None,
        description="Filter by session (e.g., 'Semester 1'). Filters out courses from other sessions."
    )
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
# Input Models - Ed Write Operations
# ============================================================================

class EdPostThreadInput(BaseModel):
    """Input parameters for posting a new Ed Discussion thread"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: int = Field(
        ...,
        description="Ed course ID (obtained from ed_list_courses)",
        gt=0
    )
    title: str = Field(
        ...,
        description="Thread title",
        min_length=1
    )
    content: str = Field(
        ...,
        description="Thread content in markdown (converted to Ed XML automatically)",
        min_length=1
    )
    thread_type: EdThreadType = Field(
        default=EdThreadType.QUESTION,
        description="Thread type: 'question' (answerable), 'post' (general), 'announcement' (staff)"
    )
    category: str = Field(
        ...,
        description="Thread category — must match an existing course category exactly (e.g., 'General', 'Assignments'; see categories in ed_list_threads output)",
        min_length=1
    )
    subcategory: str = Field(
        default="",
        description="Optional subcategory (must match an existing one)"
    )
    is_private: bool = Field(
        default=False,
        description="If true, only staff and you can see the thread"
    )
    is_anonymous: bool = Field(
        default=False,
        description="If true, your name is hidden from other students"
    )


class EdEditThreadInput(BaseModel):
    """Input parameters for editing an existing Ed Discussion thread"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    thread_id: int = Field(
        ...,
        description="Ed thread ID (your own thread, or staff permissions required)",
        gt=0
    )
    title: Optional[str] = Field(
        default=None,
        description="New title (unchanged if omitted)"
    )
    content: Optional[str] = Field(
        default=None,
        description="New content in markdown (unchanged if omitted)"
    )
    category: Optional[str] = Field(
        default=None,
        description="New category (unchanged if omitted)"
    )
    subcategory: Optional[str] = Field(
        default=None,
        description="New subcategory (unchanged if omitted)"
    )


class EdPostCommentInput(BaseModel):
    """Input parameters for posting a comment or answer on an Ed thread"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    thread_id: int = Field(
        ...,
        description="Ed thread ID to comment on",
        gt=0
    )
    content: str = Field(
        ...,
        description="Comment content in markdown (converted to Ed XML automatically)",
        min_length=1
    )
    comment_type: EdCommentType = Field(
        default=EdCommentType.COMMENT,
        description="'answer' to answer a question thread, 'comment' for a discussion comment"
    )
    is_private: bool = Field(
        default=False,
        description="If true, only staff and you can see the comment"
    )
    is_anonymous: bool = Field(
        default=False,
        description="If true, your name is hidden from other students"
    )


class EdReplyToCommentInput(BaseModel):
    """Input parameters for replying to an existing Ed comment"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    comment_id: int = Field(
        ...,
        description="Ed comment ID to reply to (from ed_get_thread JSON output)",
        gt=0
    )
    content: str = Field(
        ...,
        description="Reply content in markdown (converted to Ed XML automatically)",
        min_length=1
    )
    is_private: bool = Field(
        default=False,
        description="If true, only staff and you can see the reply"
    )
    is_anonymous: bool = Field(
        default=False,
        description="If true, your name is hidden from other students"
    )


class EdAcceptAnswerInput(BaseModel):
    """Input parameters for accepting an answer on your Ed question thread"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    thread_id: int = Field(
        ...,
        description="Ed question thread ID (must be your own thread)",
        gt=0
    )
    comment_id: int = Field(
        ...,
        description="ID of the answer comment to accept",
        gt=0
    )


class EdThreadActionInput(BaseModel):
    """Input parameters for toggling an Ed thread state"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    thread_id: int = Field(
        ...,
        description="Ed thread ID",
        gt=0
    )
    action: EdThreadAction = Field(
        ...,
        description=(
            "Action to perform. 'star'/'unstar' work for students (private bookmark); "
            "'pin'/'unpin'/'lock'/'unlock'/'endorse'/'unendorse' require staff role"
        )
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
# Input Models - Ed Resources & Workspaces
# ============================================================================

class EdListResourcesInput(BaseModel):
    """Input parameters for listing Ed course resources"""
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


class EdListWorkspacesInput(BaseModel):
    """Input parameters for listing Ed course workspaces"""
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


class EdCreateWorkspaceInput(BaseModel):
    """Input parameters for creating an Ed workspace"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: int = Field(
        ...,
        description="Ed course ID (numeric ID, can be obtained from ed_list_courses)",
        gt=0
    )
    title: str = Field(
        ...,
        description="Workspace title",
        min_length=1, max_length=200
    )
    workspace_type: str = Field(
        default="general",
        description=(
            "Environment type: 'general' (default image), or a language "
            "environment such as 'c', 'cpp', 'python', 'java', 'nodejs', "
            "'jupyter', 'rstudio'"
        ),
        min_length=1, max_length=30
    )


class EdUpdateWorkspaceInput(BaseModel):
    """Input parameters for updating an Ed workspace"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    workspace_id: str = Field(
        ...,
        description="Workspace ID (opaque string, can be obtained from ed_list_workspaces)",
        min_length=1, max_length=64
    )
    title: Optional[str] = Field(
        default=None,
        description="New workspace title",
        min_length=1, max_length=200
    )
    is_public: Optional[bool] = Field(
        default=None,
        description="Whether the workspace is visible to everyone in the course"
    )
    public_write: Optional[bool] = Field(
        default=None,
        description="Whether everyone in the course can edit the workspace"
    )


class EdDeleteWorkspaceInput(BaseModel):
    """Input parameters for deleting an Ed workspace"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    workspace_id: str = Field(
        ...,
        description="Workspace ID (opaque string, can be obtained from ed_list_workspaces)",
        min_length=1, max_length=64
    )


# ============================================================================
# Input Models - Gradescope
# ============================================================================

class GradescopeListCoursesInput(BaseModel):
    """Input parameters for listing Gradescope courses"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GradescopeListAssignmentsInput(BaseModel):
    """Input parameters for listing Gradescope assignments in a course"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Gradescope course ID (obtained from gradescope_list_courses)",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# Input Models - Cross-Verification
# ============================================================================

class VerifyAssessmentCoverageInput(BaseModel):
    """Input parameters for cross-verifying assessment coverage between Unit Outline and Canvas"""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    course_id: str = Field(
        ...,
        description="Canvas course ID (e.g., '69874')",
        min_length=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


# ============================================================================
# HTTP Client Pool (lazy initialization for TCP connection reuse)
# ============================================================================

_canvas_client: Optional[httpx.AsyncClient] = None
_ed_client: Optional[httpx.AsyncClient] = None
_general_client: Optional[httpx.AsyncClient] = None


def get_canvas_client() -> httpx.AsyncClient:
    """Get or create reusable Canvas API HTTP client."""
    global _canvas_client
    if _canvas_client is None:
        _canvas_client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    return _canvas_client


def get_ed_client() -> httpx.AsyncClient:
    """Get or create reusable Ed API HTTP client."""
    global _ed_client
    if _ed_client is None:
        _ed_client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    return _ed_client


def get_general_client() -> httpx.AsyncClient:
    """Get or create reusable general HTTP client (for unit outlines, downloads)."""
    global _general_client
    if _general_client is None:
        _general_client = httpx.AsyncClient(timeout=120, follow_redirects=True)
    return _general_client


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
    data: Optional[Dict[str, Any]] = None,
    timeout_override: Optional[int] = None
) -> Any:
    """Send Canvas API request"""
    url = f"{CANVAS_BASE_URL}{endpoint}"
    headers = get_canvas_headers()
    client = get_canvas_client()

    try:
        kwargs: Dict[str, Any] = {"headers": headers}
        if timeout_override:
            kwargs["timeout"] = httpx.Timeout(timeout_override)
        if method == "GET":
            response = await client.get(url, params=params, **kwargs)
        elif method == "POST":
            response = await client.post(url, json=data, **kwargs)
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


def _parse_next_link(link_header: str) -> Optional[str]:
    """Parse Canvas Link header to find next page URL."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None


async def canvas_api_request_paginated(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    max_pages: int = 10,
    timeout_override: Optional[int] = None,
) -> List[Any]:
    """Auto-paginate Canvas API requests using Link header."""
    all_results: List[Any] = []
    url: Optional[str] = f"{CANVAS_BASE_URL}{endpoint}"
    headers = get_canvas_headers()
    client = get_canvas_client()

    if params is None:
        params = {}
    params.setdefault("per_page", 50)

    kwargs: Dict[str, Any] = {"headers": headers}
    if timeout_override:
        kwargs["timeout"] = httpx.Timeout(timeout_override)

    page = 0
    while url and page < max_pages:
        try:
            response = await client.get(
                url, params=params if page == 0 else None, **kwargs,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                all_results.extend(data)
            else:
                all_results.append(data)

            url = _parse_next_link(response.headers.get("link", ""))
            page += 1

        except httpx.HTTPStatusError as e:
            return [_handle_canvas_error(e)]
        except httpx.TimeoutException:
            return [{"error": "Canvas request timed out. Please try again later."}]
        except Exception:
            return [{"error": "Canvas request failed. Please try again later."}]

    return all_results


def _handle_canvas_error(e: httpx.HTTPStatusError) -> Dict[str, str]:
    """Handle Canvas HTTP errors"""
    status_code = e.response.status_code
    error_messages = {
        401: "Canvas authentication failed. Please check if API token is valid.",
        403: ("Canvas permission denied. This course may restrict file listing for students. "
              "Alternative: use canvas_get_page (JSON format) to find embedded file links "
              "in course pages, then use canvas_get_file_content with the file ID."),
        404: "Canvas resource not found. Please check if the ID is correct.",
        429: "Canvas request rate limit exceeded. Please try again later."
    }
    error_msg = error_messages.get(status_code, f"Canvas API error (status code: {status_code})")
    return {"error": error_msg}


async def canvas_upload_file(upload_endpoint: str, file_path: str) -> Dict[str, Any]:
    """
    Upload a local file to Canvas using the standard three-step upload flow.

    1. POST the upload endpoint to reserve an upload slot
    2. POST the file bytes to the returned upload_url with upload_params
    3. Confirm the upload (follow the redirect / location with auth)

    Returns the Canvas file object dict, or {"error": ...} on failure.
    """
    if not os.path.isfile(file_path):
        return {"error": f"File not found: {file_path}"}

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    slot = await canvas_api_request(
        upload_endpoint, method="POST",
        data={
            "name": file_name,
            "size": file_size,
            "content_type": content_type,
            "on_duplicate": "rename"
        }
    )
    if not isinstance(slot, dict):
        return {"error": "Unexpected response when reserving Canvas upload slot."}
    if "error" in slot:
        return slot

    upload_url = slot.get("upload_url")
    upload_params = slot.get("upload_params", {})
    if not upload_url:
        return {"error": "Canvas did not return an upload URL."}

    # The storage endpoint (e.g. S3) must be called WITHOUT the Canvas auth
    # header, and the redirect it returns must be confirmed WITH it, so
    # redirects are handled manually here.
    client = get_general_client()
    try:
        with open(file_path, 'rb') as fh:
            upload_response = await client.post(
                upload_url,
                data=upload_params,
                files={"file": (file_name, fh)},
                follow_redirects=False
            )

        if 300 <= upload_response.status_code < 400:
            confirm_url = upload_response.headers.get("location", "")
            if not confirm_url:
                return {"error": "Canvas upload confirmation URL missing."}
            confirm_response = await client.get(
                confirm_url, headers=get_canvas_headers()
            )
            confirm_response.raise_for_status()
            return confirm_response.json()

        upload_response.raise_for_status()
        result = upload_response.json()
        if isinstance(result, dict) and "id" not in result and result.get("location"):
            confirm_response = await client.get(
                result["location"], headers=get_canvas_headers()
            )
            confirm_response.raise_for_status()
            return confirm_response.json()
        return result

    except httpx.HTTPStatusError as e:
        return {"error": f"File upload failed (HTTP {e.response.status_code})."}
    except httpx.TimeoutException:
        return {"error": "File upload timed out. The file may be too large."}
    except Exception:
        return {"error": "File upload failed."}


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
    """
    Send Ed Discussion API request.

    Returns parsed JSON, or None for void endpoints (e.g. accept/star
    toggles return an empty body on success), or {"error": ...} on failure.
    """
    url = f"{ED_BASE_URL}{endpoint}"
    headers = get_ed_headers()
    client = get_ed_client()

    try:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = await client.put(url, headers=headers, json=data)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        if not response.content:
            return None
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
# API Client Utilities - Gradescope
# ============================================================================

_gradescope_connection: Optional[Any] = None


def _gradescope_login() -> Any:
    """Create and log in a Gradescope session (blocking; run in a thread)."""
    from gradescopeapi.classes.connection import GSConnection

    connection = GSConnection()
    connection.login(GRADESCOPE_EMAIL, GRADESCOPE_PASSWORD)
    return connection


async def get_gradescope_connection() -> Any:
    """
    Get or create the shared Gradescope session.

    Returns the connection, or {"error": ...} when credentials are missing,
    the gradescopeapi package is absent, or login fails.
    """
    # ponytail: process-wide singleton session, no expiry handling —
    # restart the server if Gradescope invalidates the cookie
    global _gradescope_connection
    if not GRADESCOPE_EMAIL or not GRADESCOPE_PASSWORD:
        return {"error": (
            "Gradescope credentials not configured. Set GRADESCOPE_EMAIL and "
            "GRADESCOPE_PASSWORD environment variables. SSO accounts must "
            "first set a native password via 'forgot password' on gradescope.com."
        )}
    if _gradescope_connection is not None and getattr(
        _gradescope_connection, "logged_in", False
    ):
        return _gradescope_connection
    try:
        _gradescope_connection = await asyncio.to_thread(_gradescope_login)
    except ImportError:
        return {"error": (
            "gradescopeapi package not installed. Run: pip install gradescopeapi"
        )}
    except ValueError:
        return {"error": (
            "Gradescope login failed. Check GRADESCOPE_EMAIL / GRADESCOPE_PASSWORD. "
            "SSO accounts need a native password (set via 'forgot password')."
        )}
    except Exception:
        return {"error": "Gradescope connection failed. Please try again later."}
    return _gradescope_connection


def _serialize_gradescope(obj: Any) -> Any:
    """Convert gradescopeapi dataclass values into JSON-safe types"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def gradescope_asdict(obj: Any) -> Dict[str, Any]:
    """Convert a gradescopeapi dataclass to a JSON-safe dict"""
    return {
        key: _serialize_gradescope(value)
        for key, value in dataclasses.asdict(obj).items()
    }


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


def escape_ed_xml(text: str) -> str:
    """Escape text for Ed XML content (Ed itself does not escape single quotes)"""
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _format_ed_inline(text: str) -> str:
    """Convert inline markdown (code, bold, italic, links, math) to Ed XML"""
    code_spans: List[str] = []

    def _stash_code(match: "re.Match[str]") -> str:
        code_spans.append(f"<code>{escape_ed_xml(match.group(1))}</code>")
        return f"\x00CODE{len(code_spans) - 1}\x00"

    # Code spans are extracted first so escaping and other inline rules
    # never touch their contents
    text = re.sub(r'`([^`]+)`', _stash_code, text)
    text = escape_ed_xml(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<bold>\1</bold>', text)
    text = re.sub(r'(?<!\*)\*(.+?)\*(?!\*)', r'<italic>\1</italic>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<link href="\2">\1</link>', text)
    text = re.sub(r'\$([^$]+)\$', r'<math>\1</math>', text)
    for idx, span in enumerate(code_spans):
        text = text.replace(f"\x00CODE{idx}\x00", span)
    return text


def markdown_to_ed_xml(content: str) -> str:
    """
    Convert markdown to Ed's XML document format for thread/comment content.

    Content already starting with '<document' is passed through untouched.
    Supported: headings, bold/italic/inline code/links/inline math,
    fenced code blocks (with language -> snippet), bullet/numbered lists,
    and Ed callouts ('> [!info] ...' with success/info/warning/error).
    Each non-empty text line becomes its own paragraph (Ed semantics).
    """
    if content.lstrip().startswith("<document"):
        return content

    lines = content.split('\n')
    blocks: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence (tolerates unclosed fence at EOF)
            code = escape_ed_xml('\n'.join(code_lines))
            if lang:
                blocks.append(
                    f'<snippet language="{escape_ed_xml(lang)}" '
                    f'runnable="false">{code}</snippet>'
                )
            else:
                blocks.append(f'<pre>{code}</pre>')
            continue

        if not line.strip():
            i += 1
            continue

        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading:
            level = len(heading.group(1))
            blocks.append(
                f'<heading level="{level}">'
                f'{_format_ed_inline(heading.group(2))}</heading>'
            )
            i += 1
            continue

        callout = re.match(
            r'^>\s*\[!(success|info|warning|error)\]\s*(.*)$', line, re.IGNORECASE
        )
        if callout:
            callout_type = callout.group(1).lower()
            body_parts = [callout.group(2)] if callout.group(2) else []
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                body_parts.append(lines[i][2:])
                i += 1
            body = ' '.join(body_parts)
            blocks.append(
                f'<callout type="{callout_type}">'
                f'<paragraph>{_format_ed_inline(body)}</paragraph></callout>'
            )
            continue

        if re.match(r'^[-*]\s+', line):
            bullet_items: List[str] = []
            while i < len(lines) and re.match(r'^[-*]\s+', lines[i]):
                bullet_items.append(re.sub(r'^[-*]\s+', '', lines[i]))
                i += 1
            item_xml = ''.join(
                f'<list-item><paragraph>{_format_ed_inline(item)}</paragraph></list-item>'
                for item in bullet_items
            )
            blocks.append(f'<list style="bullet">{item_xml}</list>')
            continue

        if re.match(r'^\d+\.\s+', line):
            numbered_items: List[str] = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                numbered_items.append(re.sub(r'^\d+\.\s+', '', lines[i]))
                i += 1
            item_xml = ''.join(
                f'<list-item><paragraph>{_format_ed_inline(item)}</paragraph></list-item>'
                for item in numbered_items
            )
            blocks.append(f'<list style="number">{item_xml}</list>')
            continue

        blocks.append(f'<paragraph>{_format_ed_inline(line)}</paragraph>')
        i += 1

    return f'<document version="2.0">{"".join(blocks)}</document>'


def format_courses_markdown(courses: List[Dict]) -> str:
    """Format Canvas course list as Markdown"""
    if not courses:
        return "No Canvas courses found."
    
    lines = ["# My Canvas Courses\n", f"*Total {len(courses)} courses*\n"]
    
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

    # Check for locked content
    if page.get('locked_for_user'):
        lock_info = page.get('lock_info', {})
        lock_explanation = page.get('lock_explanation', 'This page is locked.')
        prereqs = lock_info.get('context_module', {}).get('name', '')
        lines = [f"# {page_title} (Locked)\n"]
        lines.append("**Status**: Locked")
        lines.append(f"**Reason**: {lock_explanation}")
        if prereqs:
            lines.append(f"**Prerequisite Module**: {prereqs}")
        return "\n".join(lines)

    body = strip_html(page.get('body', ''))
    lines = [f"# {page_title}\n"]
    lines.append(f"**Updated**: {updated_at}\n")
    lines.append("---\n")
    lines.append(body if body else "*No content*")

    return "\n".join(lines)


def format_todo_markdown(items: List[Dict]) -> str:
    """Format Canvas to-do list as Markdown"""
    if not items:
        return "Nothing on your Canvas to-do list."

    lines = ["# Canvas To-Do List\n"]
    for item in items:
        assignment = item.get('assignment') or {}
        name = assignment.get('name', item.get('type', 'Item'))
        course = item.get('context_name', '')
        due = format_datetime(assignment.get('due_at'))
        points = assignment.get('points_possible')

        lines.append(f"## {name}")
        if course:
            lines.append(f"- **Course**: {course}")
        lines.append(f"- **Due**: {due}")
        if points is not None:
            lines.append(f"- **Points**: {points}")
        lines.append("")

    return "\n".join(lines)


def format_upcoming_markdown(events: List[Dict]) -> str:
    """Format Canvas upcoming events as Markdown"""
    if not events:
        return "No upcoming Canvas events."

    lines = ["# Upcoming Canvas Events\n"]
    for event in events:
        title = event.get('title', 'Untitled')
        context = event.get('context_name', '')
        event_type = event.get('type', 'event')
        start = format_datetime(event.get('start_at'))
        context_str = f" ({context})" if context else ""
        lines.append(f"- **{title}**{context_str} — {start} [{event_type}]")

    return "\n".join(lines)


def format_missing_submissions_markdown(assignments: List[Dict]) -> str:
    """Format missing (past-due, unsubmitted) assignments as Markdown"""
    if not assignments:
        return "No missing submissions. All caught up."

    lines = [f"# Missing Submissions ({len(assignments)})\n"]
    for assignment in assignments:
        name = assignment.get('name', 'Untitled')
        course = (assignment.get('course') or {}).get('name', '')
        due = format_datetime(assignment.get('due_at'))
        points = assignment.get('points_possible')
        lines.append(f"## {name}")
        if course:
            lines.append(f"- **Course**: {course}")
        lines.append(f"- **Was due**: {due}")
        if points is not None:
            lines.append(f"- **Points**: {points}")
        lines.append("")

    return "\n".join(lines)


def classify_submission(assignment: Dict) -> str:
    """Classify an assignment's submission state for the current student"""
    submission = assignment.get('submission') or {}
    if submission.get('excused'):
        return "Excused"
    state = submission.get('workflow_state', 'unsubmitted')
    if state == 'graded':
        return "Graded"
    if state in ('submitted', 'pending_review'):
        return "Submitted"
    if submission.get('missing'):
        return "Missing"
    due_at = assignment.get('due_at')
    if due_at:
        try:
            due = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
            if due < datetime.now(due.tzinfo):
                return "Overdue"
        except ValueError:
            pass
    return "Not submitted yet"


def format_submission_status_markdown(assignments: List[Dict], course_name: str = "") -> str:
    """Format per-assignment submission status as Markdown, grouped by state"""
    if not assignments:
        return "No assignments found."

    title = f"# Submission Status - {course_name}" if course_name else "# Submission Status"
    lines = [title + "\n"]

    groups: Dict[str, List[str]] = {}
    for assignment in assignments:
        status = classify_submission(assignment)
        submission = assignment.get('submission') or {}
        name = assignment.get('name', 'Untitled')
        due = format_datetime(assignment.get('due_at'))
        entry = f"- **{name}** (due {due})"
        if status == "Graded":
            score = submission.get('score')
            points = assignment.get('points_possible')
            entry += f" — score {score}/{points}"
        if submission.get('late'):
            entry += " — late"
        groups.setdefault(status, []).append(entry)

    status_order = ["Missing", "Overdue", "Not submitted yet", "Submitted", "Graded", "Excused"]
    for status in status_order:
        if status in groups:
            lines.append(f"## {status} ({len(groups[status])})")
            lines.extend(groups[status])
            lines.append("")

    return "\n".join(lines)


def format_discussions_markdown(topics: List[Dict], course_name: str = "") -> str:
    """Format Canvas discussion topics as Markdown"""
    if not topics:
        return "No discussion topics found."

    header = f"# Discussions - {course_name}" if course_name else "# Discussions"
    lines = [header + "\n"]
    for topic in topics:
        title = topic.get('title', 'Untitled')
        replies = topic.get('discussion_subentry_count', 0)
        unread = topic.get('unread_count', 0)
        posted = format_datetime(topic.get('posted_at'))
        flags = []
        if topic.get('pinned'):
            flags.append("pinned")
        if topic.get('locked'):
            flags.append("locked")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        unread_str = f", {unread} unread" if unread else ""
        lines.append(
            f"- **{title}** (ID: {topic.get('id')}){flag_str} — "
            f"{replies} replies{unread_str} — {posted}"
        )

    return "\n".join(lines)


def format_all_grades_markdown(courses: List[Dict]) -> str:
    """Format grades for all courses (from include[]=total_scores) as Markdown"""
    graded: List[str] = []
    hidden: List[str] = []
    for course in courses:
        name = course.get('name', 'Unknown Course')
        enrollments = course.get('enrollments') or []
        student = next(
            (e for e in enrollments if e.get('type') == 'student'),
            enrollments[0] if enrollments else {}
        )
        current_score = student.get('computed_current_score')
        current_grade = student.get('computed_current_grade')
        final_score = student.get('computed_final_score')

        if course.get('hide_final_grades'):
            hidden.append(name)
            continue
        # No graded items at all (portal/hub courses): skip as noise
        if current_score is None and not final_score:
            continue

        parts = []
        if current_score is not None:
            grade_prefix = f"{current_grade} " if current_grade else ""
            parts.append(f"current {grade_prefix}{current_score}%")
        if final_score is not None:
            parts.append(f"final {final_score}% (ungraded counted as 0)")
        graded.append(f"- **{name}**: {', '.join(parts)}")

    if not graded and not hidden:
        return "No grade data available for these courses."

    lines = ["# All Course Grades\n"]
    lines.append(
        "*Canvas gradebook totals only — official results (Sydney Student) may differ.*\n"
    )
    lines.extend(graded)
    if hidden:
        lines.append(f"\n## Totals hidden by instructor ({len(hidden)})")
        lines.append(
            "*These courses disable student-visible totals; "
            "use canvas_get_grades or canvas_get_submission_status for per-assignment marks.*"
        )
        lines.extend(f"- {name}" for name in hidden)

    return "\n".join(lines)


def format_my_submission_markdown(submission: Dict) -> str:
    """Format your own submission with feedback as Markdown"""
    assignment = submission.get('assignment') or {}
    assignment_name = assignment.get('name', 'Assignment')

    lines = [f"# My Submission - {assignment_name}\n"]
    lines.append(f"- **State**: {submission.get('workflow_state', 'unknown')}")
    lines.append(f"- **Submitted at**: {format_datetime(submission.get('submitted_at'))}")

    score = submission.get('score')
    points = assignment.get('points_possible')
    if score is not None:
        lines.append(f"- **Score**: {score}/{points}")
    if submission.get('grade'):
        lines.append(f"- **Grade**: {submission['grade']}")
    if submission.get('late'):
        lines.append("- **Late**: yes")
    if submission.get('missing'):
        lines.append("- **Missing**: yes")
    if submission.get('excused'):
        lines.append("- **Excused**: yes")
    if submission.get('attempt'):
        lines.append(f"- **Attempt**: {submission['attempt']}")

    comments = submission.get('submission_comments') or []
    if comments:
        lines.append("\n## Feedback Comments")
        for comment in comments:
            author = comment.get('author_name', 'Unknown')
            created = format_datetime(comment.get('created_at'))
            text = strip_html(comment.get('comment', ''))
            lines.append(f"- **{author}** ({created}): {text}")

    rubric = submission.get('rubric_assessment') or {}
    if rubric:
        criteria_names = {
            c.get('id'): c.get('description', c.get('id'))
            for c in (assignment.get('rubric') or [])
        }
        lines.append("\n## Rubric Assessment")
        for criterion_id, assessment in rubric.items():
            name = criteria_names.get(criterion_id, criterion_id)
            rubric_points = assessment.get('points')
            rubric_comment = assessment.get('comments', '')
            entry = f"- **{name}**: {rubric_points}"
            if rubric_comment:
                entry += f" — {rubric_comment}"
            lines.append(entry)

    return "\n".join(lines)


def _format_discussion_entries(
    entries: List[Dict], participants: Dict[Any, str], depth: int = 0
) -> List[str]:
    """Recursively format discussion entries with indentation"""
    lines: List[str] = []
    indent = "  " * depth
    for entry in entries:
        if entry.get('deleted'):
            continue
        author = participants.get(entry.get('user_id'), 'Unknown')
        message = strip_html(entry.get('message', ''))
        created = format_datetime(entry.get('created_at'))
        lines.append(f"{indent}- **{author}** ({created}): {message}")
        replies = entry.get('replies') or []
        if replies:
            lines.extend(_format_discussion_entries(replies, participants, depth + 1))
    return lines


def format_discussion_detail_markdown(topic: Dict, view: Dict) -> str:
    """Format a Canvas discussion topic with threaded entries as Markdown"""
    title = topic.get('title', 'Untitled')
    author = (topic.get('author') or {}).get('display_name', 'Unknown')
    posted = format_datetime(topic.get('posted_at'))
    message = strip_html(topic.get('message', ''))

    lines = [f"# {title}\n"]
    lines.append(f"**Author**: {author} | **Posted**: {posted}\n")
    lines.append("---\n")
    lines.append(message if message else "*No content*")
    lines.append("")

    participants = {
        p.get('id'): p.get('display_name', 'Unknown')
        for p in view.get('participants', [])
    }
    entries = view.get('view', [])
    entry_lines = _format_discussion_entries(entries, participants)
    if entry_lines:
        lines.append("## Replies\n")
        lines.extend(entry_lines)
    else:
        lines.append("*No replies yet*")

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
    if table and hasattr(table, 'find_all'):
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
        if desc_el and hasattr(desc_el, 'get'):
            result["course_description"] = desc_el.get('content', '')  # type: ignore[arg-type]
    else:
        result["course_description"] = desc_el.get_text(strip=True)

    # Extract learning outcomes
    outcomes_section = soup.find('div', id='learning-outcomes') or soup.find('div', class_='learning-outcomes')
    if outcomes_section and hasattr(outcomes_section, 'find_all'):
        items = outcomes_section.find_all('li')
        result["learning_outcomes"] = [li.get_text(strip=True) for li in items]

    return result


def format_unit_outline_markdown(outline_data: Dict[str, Any]) -> str:
    """Format parsed Unit Outline data as Markdown"""
    lines = ["# Unit Outline\n"]

    if outline_data.get("course_description"):
        lines.append("## Course Description\n")
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
    
    for i, enrollment in enumerate(courses, 1):
        # Unwrap nested course object from enrollment
        course = enrollment.get('course', enrollment)

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
    lines.append("\n---\n")
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
        lines.append("\n---\n")
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


def format_ed_resources_markdown(resources: List[Dict]) -> str:
    """Format Ed course resources grouped by category"""
    if not resources:
        return "No resources found for this course."

    by_category: Dict[str, List[Dict]] = {}
    for res in resources:
        by_category.setdefault(res.get('category') or 'Uncategorized', []).append(res)

    lines = [f"# Ed Resources ({len(resources)})\n"]
    for category, items in by_category.items():
        lines.append(f"## {category} ({len(items)})")
        for res in items:
            name = res.get('name', 'Untitled')
            parts = [f"ID: {res.get('id')}"]
            if res.get('session'):
                parts.append(res['session'])
            link = res.get('link')
            if link:
                lines.append(f"- [{name}]({link}) — {', '.join(parts)}")
            else:
                ext = (res.get('extension') or '').lstrip('.').upper()
                if ext:
                    parts.append(ext)
                if res.get('size'):
                    parts.append(format_file_size(res['size']))
                lines.append(f"- **{name}** — {', '.join(parts)}")
        lines.append("")

    return "\n".join(lines)


def format_ed_workspaces_markdown(workspaces: List[Dict], users: List[Dict]) -> str:
    """Format Ed course workspaces with owner names and access flags"""
    if not workspaces:
        return "No workspaces found for this course."

    user_names = {u.get('id'): u.get('name', 'Unknown') for u in users}
    lines = [f"# Ed Workspaces ({len(workspaces)})\n"]
    for ws in workspaces:
        owner = user_names.get(ws.get('user_id'), 'Unknown')
        flags = []
        if ws.get('role'):
            flags.append(f"role: {ws['role']}")
        if ws.get('is_public'):
            flags.append("public (writable)" if ws.get('public_write') else "public")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"- **{ws.get('title', 'Untitled')}** by {owner}{flag_str}")
        lines.append(f"  - ID: `{ws.get('id')}` · created {format_datetime(ws.get('created_at'))}")

    return "\n".join(lines)


# ============================================================================
# MCP Tools - Canvas
# ============================================================================

@mcp.tool(
    name="canvas_list_courses",
    annotations={  # type: ignore[arg-type]
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
    
    result = await canvas_api_request_paginated("/courses", params=api_params)

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    return format_courses_markdown(result)


@mcp.tool(
    name="canvas_get_course",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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
    
    result = await canvas_api_request_paginated("/announcements", params=api_params)

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_announcements_markdown(result, course_name)


@mcp.tool(
    name="canvas_list_assignments",
    annotations={  # type: ignore[arg-type]
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
    
    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/assignments", params=api_params
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_assignments_markdown(result, course_name)


# ============================================================================
# MCP Tools - Canvas Grades, Files, Pages
# ============================================================================

@mcp.tool(
    name="canvas_get_grades",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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

    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/files", params=api_params
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_files_markdown(result, course_name)


@mcp.tool(
    name="canvas_get_file_content",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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

    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/pages", params=api_params
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_pages_markdown(result, course_name)


@mcp.tool(
    name="canvas_get_page",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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

    timeout = 60 if params.include_items else None
    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/modules",
        params=api_params,
        timeout_override=timeout,
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_modules_markdown(result, course_name)


@mcp.tool(
    name="canvas_list_module_items",
    annotations={  # type: ignore[arg-type]
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

    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/modules/{params.module_id}/items",
        params=api_params,
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

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
    annotations={  # type: ignore[arg-type]
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
    lines.append("\nUse `fetch_unit_outline` with this URL to get the assessment structure.")

    return "\n".join(lines)


@mcp.tool(
    name="fetch_unit_outline",
    annotations={  # type: ignore[arg-type]
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
    client = get_general_client()
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
    annotations={  # type: ignore[arg-type]
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

    result = await canvas_api_request_paginated("/calendar_events", params=api_params)

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    return format_calendar_markdown(result)


@mcp.tool(
    name="canvas_get_syllabus",
    annotations={  # type: ignore[arg-type]
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
# MCP Tools - Canvas Student Dashboard
# ============================================================================

@mcp.tool(
    name="canvas_get_todo",
    annotations={  # type: ignore[arg-type]
        "title": "Get Canvas To-Do List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_todo(params: GetTodoInput) -> str:
    """
    Get the current user's Canvas to-do list across all courses.

    Returns assignments that need to be submitted, sorted by Canvas relevance.
    This is the same list shown in the Canvas dashboard sidebar.

    Args:
        params (GetTodoInput): Input parameters

    Returns:
        str: To-do items with course, due date, and points
    """
    result = await canvas_api_request_paginated(
        "/users/self/todo", params={"per_page": params.limit}
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    items = result[:params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(items, indent=2, ensure_ascii=False)

    return format_todo_markdown(items)


@mcp.tool(
    name="canvas_get_upcoming",
    annotations={  # type: ignore[arg-type]
        "title": "Get Canvas Upcoming Events",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_upcoming(params: GetUpcomingInput) -> str:
    """
    Get the current user's upcoming Canvas events and assignment deadlines.

    Covers the near future across all enrolled courses (same as the
    "Coming Up" section in the Canvas dashboard).

    Args:
        params (GetUpcomingInput): Input parameters

    Returns:
        str: Upcoming events with dates
    """
    result = await canvas_api_request("/users/self/upcoming_events")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    events = result if isinstance(result, list) else []

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(events, indent=2, ensure_ascii=False)

    return format_upcoming_markdown(events)


@mcp.tool(
    name="canvas_get_missing_submissions",
    annotations={  # type: ignore[arg-type]
        "title": "Get Canvas Missing Submissions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_missing_submissions(params: GetMissingSubmissionsInput) -> str:
    """
    Get assignments that are past due and still unsubmitted.

    Args:
        params (GetMissingSubmissionsInput): Input parameters
            - course_ids: Optional list of Canvas course IDs to filter

    Returns:
        str: Missing assignments with course and original due date
    """
    api_params: Dict[str, Any] = {
        "include[]": ["course"],
        "per_page": params.limit
    }
    if params.course_ids:
        api_params["course_ids[]"] = params.course_ids

    result = await canvas_api_request_paginated(
        "/users/self/missing_submissions", params=api_params
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    assignments = result[:params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(assignments, indent=2, ensure_ascii=False)

    return format_missing_submissions_markdown(assignments)


@mcp.tool(
    name="canvas_get_submission_status",
    annotations={  # type: ignore[arg-type]
        "title": "Get Canvas Submission Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_submission_status(params: GetSubmissionStatusInput) -> str:
    """
    Get per-assignment submission status for a Canvas course.

    Groups assignments by state: Missing / Overdue / Not submitted yet /
    Submitted / Graded / Excused. Shows scores for graded work and flags
    late submissions.

    Args:
        params (GetSubmissionStatusInput): Input parameters

    Returns:
        str: Assignments grouped by submission state
    """
    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/assignments",
        params={"include[]": ["submission"], "order_by": "due_at"}
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        status_data = [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "due_at": a.get("due_at"),
                "points_possible": a.get("points_possible"),
                "status": classify_submission(a),
                "submission": a.get("submission")
            }
            for a in result
        ]
        return json.dumps(status_data, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_submission_status_markdown(result, course_name)


@mcp.tool(
    name="canvas_list_discussions",
    annotations={  # type: ignore[arg-type]
        "title": "Get Canvas Discussion Topics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_list_discussions(params: ListDiscussionsInput) -> str:
    """
    Get discussion topics for a Canvas course.

    Sorted by recent activity. Shows reply counts, unread counts,
    and pinned/locked status. Use canvas_get_discussion to read a topic.

    Args:
        params (ListDiscussionsInput): Input parameters

    Returns:
        str: Discussion topic list
    """
    result = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/discussion_topics",
        params={"order_by": "recent_activity", "per_page": params.limit}
    )

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    topics = result[:params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(topics, indent=2, ensure_ascii=False)

    course_name = await get_course_name(params.course_id)
    return format_discussions_markdown(topics, course_name)


@mcp.tool(
    name="canvas_get_discussion",
    annotations={  # type: ignore[arg-type]
        "title": "Get Canvas Discussion Topic",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_discussion(params: GetDiscussionInput) -> str:
    """
    Get a Canvas discussion topic with its full threaded replies.

    Args:
        params (GetDiscussionInput): Input parameters
            - course_id: Canvas course ID
            - topic_id: Discussion topic ID (from canvas_list_discussions)

    Returns:
        str: Topic content and threaded replies with authors
    """
    topic = await canvas_api_request(
        f"/courses/{params.course_id}/discussion_topics/{params.topic_id}"
    )

    if isinstance(topic, dict) and "error" in topic:
        return f"Error: {topic['error']}"

    view = await canvas_api_request(
        f"/courses/{params.course_id}/discussion_topics/{params.topic_id}/view"
    )

    if isinstance(view, dict) and "error" in view:
        return f"Error: {view['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"topic": topic, "view": view}, indent=2, ensure_ascii=False)

    return format_discussion_detail_markdown(topic, view)


@mcp.tool(
    name="canvas_get_all_grades",
    annotations={  # type: ignore[arg-type]
        "title": "Get All Canvas Course Grades",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_all_grades(params: GetAllGradesInput) -> str:
    """
    Get current grades for ALL your Canvas courses in one call.

    Uses include[]=total_scores so no per-course requests are needed.
    For a detailed per-assignment breakdown in one course, use
    canvas_get_grades instead.

    Args:
        params (GetAllGradesInput): Input parameters

    Returns:
        str: Course list with current/final scores and letter grades
    """
    api_params: Dict[str, Any] = {
        "include[]": ["total_scores", "current_grading_period_scores"],
        "per_page": 100
    }
    if params.enrollment_state != EnrollmentState.ALL:
        api_params["enrollment_state"] = params.enrollment_state.value

    result = await canvas_api_request_paginated("/courses", params=api_params)

    if result and isinstance(result[0], dict) and "error" in result[0]:
        return f"Error: {result[0]['error']}"

    if params.response_format == ResponseFormat.JSON:
        grades = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "enrollments": c.get("enrollments")
            }
            for c in result
        ]
        return json.dumps(grades, indent=2, ensure_ascii=False)

    return format_all_grades_markdown(result)


@mcp.tool(
    name="canvas_get_my_submission",
    annotations={  # type: ignore[arg-type]
        "title": "Get My Canvas Submission & Feedback",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_my_submission(params: GetMySubmissionInput) -> str:
    """
    Get your own submission for an assignment, including marker feedback:
    score, grade, submission comments, and rubric assessment.

    Args:
        params (GetMySubmissionInput): Input parameters

    Returns:
        str: Submission state, score, feedback comments, and rubric marks
    """
    result = await canvas_api_request(
        f"/courses/{params.course_id}/assignments/"
        f"{params.assignment_id}/submissions/self",
        params={
            "include[]": ["submission_comments", "rubric_assessment", "assignment"]
        }
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(result, indent=2, ensure_ascii=False)

    return format_my_submission_markdown(result)


@mcp.tool(
    name="canvas_get_peer_reviews",
    annotations={  # type: ignore[arg-type]
        "title": "Get My Canvas Peer Reviews",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_get_peer_reviews(params: GetPeerReviewsInput) -> str:
    """
    Get peer reviews assigned TO YOU in a Canvas course.

    Scans assignments with peer reviews enabled and lists your review
    assignments with completion status.

    Args:
        params (GetPeerReviewsInput): Input parameters

    Returns:
        str: Your peer review assignments grouped by assignment
    """
    me = await canvas_api_request("/users/self")
    if isinstance(me, dict) and "error" in me:
        return f"Error: {me['error']}"
    my_id = me.get("id")

    assignments = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/assignments", params={"per_page": 100}
    )
    if assignments and isinstance(assignments[0], dict) and "error" in assignments[0]:
        return f"Error: {assignments[0]['error']}"

    peer_assignments = [a for a in assignments if a.get("peer_reviews")]
    if not peer_assignments:
        return "No assignments with peer reviews in this course."

    my_reviews: List[Dict[str, Any]] = []
    for assignment in peer_assignments:
        reviews = await canvas_api_request_paginated(
            f"/courses/{params.course_id}/assignments/"
            f"{assignment['id']}/peer_reviews",
            params={"include[]": ["user"], "per_page": 100}
        )
        if reviews and isinstance(reviews[0], dict) and "error" in reviews[0]:
            continue
        for review in reviews:
            if review.get("assessor_id") == my_id:
                my_reviews.append({
                    "assignment_name": assignment.get("name"),
                    "assignment_id": assignment.get("id"),
                    "workflow_state": review.get("workflow_state"),
                    "reviewee": (review.get("user") or {}).get(
                        "display_name", f"user {review.get('user_id')}"
                    ),
                })

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(my_reviews, indent=2, ensure_ascii=False)

    if not my_reviews:
        return "No peer reviews assigned to you in this course."

    lines = ["# My Peer Reviews\n"]
    for review in my_reviews:
        status = "done" if review["workflow_state"] == "completed" else "PENDING"
        lines.append(
            f"- **{review['assignment_name']}** — review {review['reviewee']} "
            f"[{status}]"
        )

    return "\n".join(lines)


# ============================================================================
# MCP Tools - Canvas Write Operations
# ============================================================================

@mcp.tool(
    name="canvas_submit_assignment",
    annotations={  # type: ignore[arg-type]
        "title": "Submit Canvas Assignment",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def canvas_submit_assignment(params: SubmitAssignmentInput) -> str:
    """
    Submit a Canvas assignment on behalf of the current user.

    Supports three submission types:
    - online_text_entry: submits 'body' as the text content
    - online_url: submits 'url'
    - online_upload: uploads local 'file_paths' then attaches them

    This performs a REAL submission that markers can see. Verify the
    assignment ID and content carefully before calling.

    Args:
        params (SubmitAssignmentInput): Input parameters

    Returns:
        str: Submission confirmation with timestamp and attempt number
    """
    submission_data: Dict[str, Any] = {
        "submission_type": params.submission_type.value
    }
    uploaded_names: List[str] = []

    if params.submission_type == SubmissionType.TEXT:
        if not params.body:
            return "Error: 'body' is required for online_text_entry submissions."
        submission_data["body"] = params.body
    elif params.submission_type == SubmissionType.URL:
        if not params.url:
            return "Error: 'url' is required for online_url submissions."
        submission_data["url"] = params.url
    else:
        if not params.file_paths:
            return "Error: 'file_paths' is required for online_upload submissions."
        file_ids: List[Any] = []
        for path in params.file_paths:
            file_info = await canvas_upload_file(
                f"/courses/{params.course_id}/assignments/"
                f"{params.assignment_id}/submissions/self/files",
                path
            )
            if "error" in file_info:
                return f"Error uploading {path}: {file_info['error']}"
            if "id" not in file_info:
                return f"Error uploading {path}: Canvas did not return a file ID."
            file_ids.append(file_info["id"])
            uploaded_names.append(
                file_info.get("display_name", os.path.basename(path))
            )
        submission_data["file_ids"] = file_ids

    payload: Dict[str, Any] = {"submission": submission_data}
    if params.comment:
        payload["comment"] = {"text_comment": params.comment}

    result = await canvas_api_request(
        f"/courses/{params.course_id}/assignments/{params.assignment_id}/submissions",
        method="POST", data=payload
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    lines = ["# Submission Successful\n"]
    lines.append(f"- **Type**: {params.submission_type.value}")
    lines.append(f"- **Submitted at**: {format_datetime(result.get('submitted_at'))}")
    if result.get('attempt'):
        lines.append(f"- **Attempt**: {result['attempt']}")
    if uploaded_names:
        lines.append(f"- **Files**: {', '.join(uploaded_names)}")
    if result.get('late'):
        lines.append("- **Note**: Canvas marked this submission as LATE")

    return "\n".join(lines)


@mcp.tool(
    name="canvas_post_discussion_entry",
    annotations={  # type: ignore[arg-type]
        "title": "Post to Canvas Discussion",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def canvas_post_discussion_entry(params: PostDiscussionEntryInput) -> str:
    """
    Post a new entry (or a reply to an existing entry) in a Canvas discussion.

    This posts publicly to the course discussion as the current user.

    Args:
        params (PostDiscussionEntryInput): Input parameters
            - reply_to_entry_id: If provided, replies to that entry instead
              of creating a top-level entry

    Returns:
        str: Confirmation with the new entry ID
    """
    if params.reply_to_entry_id:
        endpoint = (
            f"/courses/{params.course_id}/discussion_topics/"
            f"{params.topic_id}/entries/{params.reply_to_entry_id}/replies"
        )
    else:
        endpoint = (
            f"/courses/{params.course_id}/discussion_topics/"
            f"{params.topic_id}/entries"
        )

    result = await canvas_api_request(
        endpoint, method="POST", data={"message": params.message}
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    lines = ["# Posted Successfully\n"]
    lines.append(f"- **Entry ID**: {result.get('id')}")
    lines.append(f"- **Posted at**: {format_datetime(result.get('created_at'))}")

    return "\n".join(lines)


# ============================================================================
# MCP Tools - Ed Discussion
# ============================================================================

@mcp.tool(
    name="ed_get_user_info",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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
    Supports optional year and session filters to reduce response size.

    Args:
        params (EdListCoursesInput): Input parameters

    Returns:
        str: Ed course list
    """
    result = await ed_api_request("/user")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    courses = result.get('courses', [])

    # Apply client-side year/session filters
    if params.year or params.session:
        filtered = []
        for enrollment in courses:
            course = enrollment.get('course', enrollment)
            if params.year and str(course.get('year', '')) != params.year:
                continue
            if params.session and course.get('session', '') != params.session:
                continue
            filtered.append(enrollment)
        courses = filtered

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(courses, indent=2, ensure_ascii=False)

    return format_ed_courses_markdown(courses)


@mcp.tool(
    name="ed_list_threads",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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
# MCP Tools - Ed Write Operations
# ============================================================================

@mcp.tool(
    name="ed_post_thread",
    annotations={  # type: ignore[arg-type]
        "title": "Post Ed Discussion Thread",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ed_post_thread(params: EdPostThreadInput) -> str:
    """
    Post a new thread to an Ed Discussion course forum.

    Content is written in markdown and converted to Ed's XML format
    automatically (headings, bold/italic, code spans, fenced code blocks,
    lists, links, math, and '> [!info]' style callouts are supported).

    This posts a REAL thread visible to the course (unless is_private).
    The post is immediately live — there is no draft stage.

    Args:
        params (EdPostThreadInput): Input parameters

    Returns:
        str: Confirmation with the new thread's number and URL
    """
    payload = {
        "thread": {
            "type": params.thread_type.value,
            "title": params.title,
            "category": params.category,
            "subcategory": params.subcategory,
            "content": markdown_to_ed_xml(params.content),
            "is_private": params.is_private,
            "is_anonymous": params.is_anonymous,
            "is_pinned": False,
            "is_megathread": False,
            "anonymous_comments": False,
        }
    }

    result = await ed_api_request(
        f"/courses/{params.course_id}/threads", method="POST", data=payload
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    thread = result.get('thread', {}) if isinstance(result, dict) else {}

    lines = ["# Thread Posted\n"]
    lines.append(f"- **Title**: {thread.get('title', params.title)}")
    lines.append(f"- **Thread ID**: {thread.get('id')}")
    lines.append(f"- **Number**: #{thread.get('number')}")
    lines.append(f"- **Type**: {thread.get('type', params.thread_type.value)}")
    if thread.get('is_private'):
        lines.append("- **Visibility**: private (staff + you only)")
    lines.append(
        f"- **URL**: https://edstem.org/au/courses/{params.course_id}"
        f"/discussion/{thread.get('id')}"
    )

    return "\n".join(lines)


@mcp.tool(
    name="ed_edit_thread",
    annotations={  # type: ignore[arg-type]
        "title": "Edit Ed Discussion Thread",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_edit_thread(params: EdEditThreadInput) -> str:
    """
    Edit an existing Ed Discussion thread (typically your own).

    Only provided fields change; everything else is preserved
    (read-modify-write against the live thread).

    Args:
        params (EdEditThreadInput): Input parameters

    Returns:
        str: Confirmation of the edit
    """
    current = await ed_api_request(f"/threads/{params.thread_id}")

    if isinstance(current, dict) and "error" in current:
        return f"Error: {current['error']}"

    thread = current.get('thread') if isinstance(current, dict) else None
    if not isinstance(thread, dict):
        return "Error: Could not load the current thread."

    changes: Dict[str, Any] = {}
    if params.title is not None:
        changes["title"] = params.title
    if params.content is not None:
        changes["content"] = markdown_to_ed_xml(params.content)
    if params.category is not None:
        changes["category"] = params.category
    if params.subcategory is not None:
        changes["subcategory"] = params.subcategory

    if not changes:
        return "Error: Nothing to change — provide at least one field."

    merged = {**thread, **changes}
    result = await ed_api_request(
        f"/threads/{params.thread_id}", method="PUT", data={"thread": merged}
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    updated = result.get('thread', {}) if isinstance(result, dict) else {}
    lines = ["# Thread Updated\n"]
    lines.append(f"- **Thread ID**: {params.thread_id}")
    lines.append(f"- **Title**: {updated.get('title', merged.get('title'))}")
    lines.append(f"- **Changed fields**: {', '.join(changes.keys())}")

    return "\n".join(lines)


@mcp.tool(
    name="ed_post_comment",
    annotations={  # type: ignore[arg-type]
        "title": "Post Ed Comment or Answer",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ed_post_comment(params: EdPostCommentInput) -> str:
    """
    Post a comment or an answer on an Ed Discussion thread.

    Use comment_type='answer' to answer a question thread (shows in the
    Answers section); 'comment' for general discussion. Content is
    markdown, converted to Ed XML automatically. Posts are immediately
    live and visible to the course (unless is_private).

    Args:
        params (EdPostCommentInput): Input parameters

    Returns:
        str: Confirmation with the new comment ID
    """
    payload = {
        "comment": {
            "type": params.comment_type.value,
            "content": markdown_to_ed_xml(params.content),
            "is_private": params.is_private,
            "is_anonymous": params.is_anonymous,
        }
    }

    result = await ed_api_request(
        f"/threads/{params.thread_id}/comments", method="POST", data=payload
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    comment = result.get('comment', {}) if isinstance(result, dict) else {}
    lines = ["# Comment Posted\n"]
    lines.append(f"- **Comment ID**: {comment.get('id')}")
    lines.append(f"- **Type**: {comment.get('type', params.comment_type.value)}")
    lines.append(f"- **Thread**: {params.thread_id}")

    return "\n".join(lines)


@mcp.tool(
    name="ed_reply_to_comment",
    annotations={  # type: ignore[arg-type]
        "title": "Reply to Ed Comment",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ed_reply_to_comment(params: EdReplyToCommentInput) -> str:
    """
    Reply to an existing comment on an Ed Discussion thread.

    Content is markdown, converted to Ed XML automatically.
    The reply is immediately live.

    Args:
        params (EdReplyToCommentInput): Input parameters

    Returns:
        str: Confirmation with the new reply ID
    """
    payload = {
        "comment": {
            "type": "comment",
            "content": markdown_to_ed_xml(params.content),
            "is_private": params.is_private,
            "is_anonymous": params.is_anonymous,
        }
    }

    result = await ed_api_request(
        f"/comments/{params.comment_id}/comments", method="POST", data=payload
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    comment = result.get('comment', {}) if isinstance(result, dict) else {}
    lines = ["# Reply Posted\n"]
    lines.append(f"- **Reply ID**: {comment.get('id')}")
    lines.append(f"- **In reply to comment**: {params.comment_id}")

    return "\n".join(lines)


@mcp.tool(
    name="ed_accept_answer",
    annotations={  # type: ignore[arg-type]
        "title": "Accept Ed Answer",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_accept_answer(params: EdAcceptAnswerInput) -> str:
    """
    Accept an answer on your Ed question thread, marking it resolved.

    Args:
        params (EdAcceptAnswerInput): Input parameters
            - thread_id: Your question thread
            - comment_id: The answer to accept (from ed_get_thread JSON output)

    Returns:
        str: Confirmation
    """
    result = await ed_api_request(
        f"/threads/{params.thread_id}/accept/{params.comment_id}", method="POST"
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    return (
        f"Answer {params.comment_id} accepted on thread {params.thread_id}. "
        "The thread is now marked as resolved."
    )


@mcp.tool(
    name="ed_thread_action",
    annotations={  # type: ignore[arg-type]
        "title": "Toggle Ed Thread State",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_thread_action(params: EdThreadActionInput) -> str:
    """
    Toggle a state on an Ed thread: star/unstar (student bookmark),
    pin/unpin, lock/unlock, endorse/unendorse (these six require staff role).

    Starring is private to your account and freely reversible.

    Args:
        params (EdThreadActionInput): Input parameters

    Returns:
        str: Confirmation
    """
    result = await ed_api_request(
        f"/threads/{params.thread_id}/{params.action.value}", method="POST"
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    return f"Thread {params.thread_id}: '{params.action.value}' applied."


# ============================================================================
# MCP Tools - Ed Lessons
# ============================================================================

@mcp.tool(
    name="ed_list_lessons",
    annotations={  # type: ignore[arg-type]
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
    annotations={  # type: ignore[arg-type]
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
# MCP Tools - Ed Resources & Workspaces
# ============================================================================

@mcp.tool(
    name="ed_list_resources",
    annotations={  # type: ignore[arg-type]
        "title": "Get Ed Resources List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_list_resources(params: EdListResourcesInput) -> str:
    """
    List the Resources tab of an Ed course (lecture slides, links, files).

    Returns resources grouped by category (e.g. Lectures, Links, General)
    with week/session labels, file types, sizes, and external link URLs.

    Args:
        params (EdListResourcesInput): Input parameters

    Returns:
        str: Resource list (Markdown or JSON format)
    """
    result = await ed_api_request(f"/courses/{params.course_id}/resources")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    resources = result.get('resources', []) if isinstance(result, dict) else []

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(resources, indent=2, ensure_ascii=False)

    return format_ed_resources_markdown(resources)


@mcp.tool(
    name="ed_list_workspaces",
    annotations={  # type: ignore[arg-type]
        "title": "Get Ed Workspaces List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_list_workspaces(params: EdListWorkspacesInput) -> str:
    """
    List workspaces (cloud IDE instances) of an Ed course.

    Includes your own workspaces and public ones shared by staff.
    Workspace IDs are opaque strings used by the other workspace tools.

    Args:
        params (EdListWorkspacesInput): Input parameters

    Returns:
        str: Workspace list (Markdown or JSON format)
    """
    result = await ed_api_request(f"/courses/{params.course_id}/workspaces")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    workspaces = result.get('workspaces', []) if isinstance(result, dict) else []
    users = result.get('users', []) if isinstance(result, dict) else []

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"workspaces": workspaces, "users": users},
                          indent=2, ensure_ascii=False)

    return format_ed_workspaces_markdown(workspaces, users)


@mcp.tool(
    name="ed_create_workspace",
    annotations={  # type: ignore[arg-type]
        "title": "Create Ed Workspace",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ed_create_workspace(params: EdCreateWorkspaceInput) -> str:
    """
    Create a new workspace (cloud IDE instance) in an Ed course.

    The workspace is created immediately under your account. Use
    workspace_type to pick the environment (e.g. 'c' for a C toolchain,
    'jupyter' for notebooks); 'general' gives the default image.

    Args:
        params (EdCreateWorkspaceInput): Input parameters

    Returns:
        str: Confirmation with the new workspace ID
    """
    payload = {
        "workspace": {
            "title": params.title,
            "type": params.workspace_type,
        }
    }
    result = await ed_api_request(
        f"/courses/{params.course_id}/workspaces", method="POST", data=payload
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    workspace = result.get('workspace', {}) if isinstance(result, dict) else {}
    lines = ["# Workspace Created\n"]
    lines.append(f"- **Workspace ID**: `{workspace.get('id')}`")
    lines.append(f"- **Title**: {workspace.get('title', params.title)}")
    lines.append(f"- **Type**: {workspace.get('type', params.workspace_type)}")

    return "\n".join(lines)


@mcp.tool(
    name="ed_update_workspace",
    annotations={  # type: ignore[arg-type]
        "title": "Update Ed Workspace",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_update_workspace(params: EdUpdateWorkspaceInput) -> str:
    """
    Update an Ed workspace you own (rename or change sharing).

    Only provided fields change; everything else is preserved
    (read-modify-write against the live workspace).

    Args:
        params (EdUpdateWorkspaceInput): Input parameters

    Returns:
        str: Confirmation of the update
    """
    current = await ed_api_request(f"/workspaces/{params.workspace_id}")

    if isinstance(current, dict) and "error" in current:
        return f"Error: {current['error']}"

    workspace = current.get('workspace') if isinstance(current, dict) else None
    if not isinstance(workspace, dict):
        return "Error: Could not load the current workspace."

    changes: Dict[str, Any] = {}
    if params.title is not None:
        changes["title"] = params.title
    if params.is_public is not None:
        changes["is_public"] = params.is_public
    if params.public_write is not None:
        changes["public_write"] = params.public_write

    if not changes:
        return "Error: Nothing to change — provide at least one field."

    merged = {**workspace, **changes}
    result = await ed_api_request(
        f"/workspaces/{params.workspace_id}", method="PUT",
        data={"workspace": merged}
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    updated = result.get('workspace', {}) if isinstance(result, dict) else {}
    lines = ["# Workspace Updated\n"]
    lines.append(f"- **Workspace ID**: `{params.workspace_id}`")
    lines.append(f"- **Title**: {updated.get('title', merged.get('title'))}")
    lines.append(f"- **Changed fields**: {', '.join(changes.keys())}")

    return "\n".join(lines)


@mcp.tool(
    name="ed_delete_workspace",
    annotations={  # type: ignore[arg-type]
        "title": "Delete Ed Workspace",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ed_delete_workspace(params: EdDeleteWorkspaceInput) -> str:
    """
    Permanently delete an Ed workspace you own.

    This removes the workspace and all files inside it and cannot be
    undone. Only delete workspaces you created.

    Args:
        params (EdDeleteWorkspaceInput): Input parameters

    Returns:
        str: Confirmation of the deletion
    """
    result = await ed_api_request(
        f"/workspaces/{params.workspace_id}", method="DELETE"
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    return f"Workspace `{params.workspace_id}` deleted."


# ============================================================================
# MCP Tools - Gradescope
# ============================================================================

@mcp.tool(
    name="gradescope_list_courses",
    annotations={  # type: ignore[arg-type]
        "title": "Get Gradescope Courses",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def gradescope_list_courses(params: GradescopeListCoursesInput) -> str:
    """
    Get all Gradescope courses for the configured account.

    Requires GRADESCOPE_EMAIL / GRADESCOPE_PASSWORD environment variables
    (Gradescope has no official API; this uses a maintained scraping library).

    Args:
        params (GradescopeListCoursesInput): Input parameters

    Returns:
        str: Courses grouped by role (student / instructor) with IDs
    """
    connection = await get_gradescope_connection()
    if isinstance(connection, dict):
        return f"Error: {connection['error']}"

    try:
        courses = await asyncio.to_thread(connection.account.get_courses)
    except Exception:
        return "Error: Failed to fetch Gradescope courses."

    if params.response_format == ResponseFormat.JSON:
        serializable = {
            role: {cid: gradescope_asdict(course) for cid, course in role_courses.items()}
            for role, role_courses in courses.items()
        }
        return json.dumps(serializable, indent=2, ensure_ascii=False)

    lines = ["# Gradescope Courses\n"]
    for role in ("student", "instructor"):
        role_courses = courses.get(role) or {}
        if not role_courses:
            continue
        lines.append(f"## As {role}")
        for course_id, course in role_courses.items():
            term = f"{course.semester} {course.year}".strip()
            name = course.full_name or course.name
            # num_assignments is display text scraped from Gradescope
            # (e.g. "2 assignments"), not a number
            count = course.num_assignments
            count_str = f" — {count}" if count else ""
            lines.append(f"- **{name}** (ID: {course_id}) — {term}{count_str}")
        lines.append("")

    if len(lines) == 1:
        return "No Gradescope courses found for this account."

    return "\n".join(lines)


@mcp.tool(
    name="gradescope_list_assignments",
    annotations={  # type: ignore[arg-type]
        "title": "Get Gradescope Assignments",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def gradescope_list_assignments(params: GradescopeListAssignmentsInput) -> str:
    """
    Get all assignments in a Gradescope course with due dates,
    submission status, and grades.

    Args:
        params (GradescopeListAssignmentsInput): Input parameters
            - course_id: Gradescope course ID (from gradescope_list_courses)

    Returns:
        str: Assignments with release/due dates, status, and grade
    """
    connection = await get_gradescope_connection()
    if isinstance(connection, dict):
        return f"Error: {connection['error']}"

    try:
        assignments = await asyncio.to_thread(
            connection.account.get_assignments, params.course_id
        )
    except Exception:
        return (
            "Error: Failed to fetch Gradescope assignments. "
            "Check the course ID (from gradescope_list_courses)."
        )

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            [gradescope_asdict(a) for a in assignments],
            indent=2, ensure_ascii=False
        )

    if not assignments:
        return "No assignments found in this Gradescope course."

    lines = [f"# Gradescope Assignments ({len(assignments)})\n"]
    for assignment in assignments:
        due = (
            assignment.due_date.strftime("%Y-%m-%d %H:%M")
            if assignment.due_date else "No due date"
        )
        status = assignment.submissions_status or "Unknown"
        grade_str = ""
        if assignment.grade is not None and assignment.max_grade is not None:
            grade_str = f" — {assignment.grade}/{assignment.max_grade}"
        lines.append(f"## {assignment.name}")
        lines.append(f"- **Due**: {due}")
        if assignment.late_due_date:
            lines.append(
                f"- **Late due**: {assignment.late_due_date.strftime('%Y-%m-%d %H:%M')}"
            )
        lines.append(f"- **Status**: {status}{grade_str}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# MCP Tools - Cross-Verification
# ============================================================================

@mcp.tool(
    name="verify_assessment_coverage",
    annotations={  # type: ignore[arg-type]
        "title": "Verify Assessment Coverage",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def verify_assessment_coverage(params: VerifyAssessmentCoverageInput) -> str:
    """
    Cross-verify assessment coverage between Unit Outline and Canvas assignments.

    Fetches the Unit Outline assessment count (via course tabs -> external tool -> HTML parse)
    and Canvas assignments count, then compares them and warns if there is a mismatch.

    Args:
        params (VerifyAssessmentCoverageInput): Input parameters

    Returns:
        str: Verification result with match/mismatch details
    """
    course_name = await get_course_name(params.course_id)

    # Step 1: Get Canvas assignments
    assignment_params: Dict[str, Any] = {"per_page": MAX_PAGE_SIZE, "order_by": "due_at"}
    canvas_assignments = await canvas_api_request_paginated(
        f"/courses/{params.course_id}/assignments", params=assignment_params
    )

    if canvas_assignments and isinstance(canvas_assignments[0], dict) and "error" in canvas_assignments[0]:
        return f"Error fetching Canvas assignments: {canvas_assignments[0]['error']}"

    # Step 2: Get Unit Outline URL from course tabs
    tabs = await canvas_api_request(f"/courses/{params.course_id}/tabs")

    if isinstance(tabs, dict) and "error" in tabs:
        return f"Error fetching course tabs: {tabs['error']}"

    outline_tab = None
    if isinstance(tabs, list):
        for tab in tabs:
            if 'Unit Outline' in tab.get('label', ''):
                outline_tab = tab
                break

    outline_assessments: List[Dict[str, Any]] = []
    outline_status = "not_found"

    if outline_tab:
        tab_id = str(outline_tab.get('id', ''))
        tool_id = tab_id.replace(CANVAS_EXTERNAL_TOOL_TAB_PREFIX, '')

        if tool_id and tool_id != tab_id:
            tool = await canvas_api_request(f"/courses/{params.course_id}/external_tools/{tool_id}")

            if isinstance(tool, dict) and "error" not in tool:
                unit_outline_url = tool.get('custom_fields', {}).get('url', '')

                if unit_outline_url:
                    # Fetch and parse Unit Outline HTML
                    client = get_general_client()
                    try:
                        response = await client.get(unit_outline_url)
                        response.raise_for_status()
                        outline_data = parse_unit_outline_html(response.text)
                        outline_assessments = outline_data.get("assessment_structure", [])
                        outline_status = "ok"
                    except Exception:
                        outline_status = "fetch_error"
                else:
                    outline_status = "no_url"
            else:
                outline_status = "tool_error"
        else:
            outline_status = "bad_tab_id"

    # Step 3: Compare counts
    canvas_count = len(canvas_assignments)
    outline_count = len(outline_assessments)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "course_id": params.course_id,
            "course_name": course_name,
            "canvas_assignment_count": canvas_count,
            "unit_outline_assessment_count": outline_count,
            "outline_status": outline_status,
            "match": canvas_count == outline_count,
            "canvas_assignments": [a.get("name", "") for a in canvas_assignments],
            "outline_assessments": [a.get("name", "") for a in outline_assessments],
        }, indent=2, ensure_ascii=False)

    # Format as Markdown
    title = "# Assessment Coverage Verification"
    if course_name:
        title += f" - {course_name}"
    title += "\n"

    lines = [title]

    # Outline status
    if outline_status != "ok":
        status_messages = {
            "not_found": "No Unit Outline tab found for this course.",
            "fetch_error": "Failed to fetch Unit Outline page.",
            "no_url": "Unit Outline URL not found in external tool configuration.",
            "tool_error": "Failed to fetch external tool details.",
            "bad_tab_id": "Could not extract tool ID from tab.",
        }
        lines.append(f"**Unit Outline**: {status_messages.get(outline_status, 'Unknown error')}")
        lines.append(f"**Canvas Assignments**: {canvas_count}\n")
        lines.append("Cannot perform comparison — Unit Outline data unavailable.")
        return "\n".join(lines)

    # Comparison result
    if canvas_count == outline_count:
        lines.append("**Status**: MATCH\n")
    else:
        lines.append("**Status**: MISMATCH\n")

    lines.append("| Source | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Unit Outline Assessments | {outline_count} |")
    lines.append(f"| Canvas Assignments | {canvas_count} |")
    lines.append("")

    if canvas_count != outline_count:
        diff = abs(canvas_count - outline_count)
        if canvas_count > outline_count:
            lines.append(f"**Warning**: Canvas has {diff} more assignment(s) than the Unit Outline.")
        else:
            lines.append(f"**Warning**: Unit Outline has {diff} more assessment(s) than Canvas.")
        lines.append("This may indicate missing assignments or extra items on either side.\n")

    # List details
    if outline_assessments:
        lines.append("## Unit Outline Assessments\n")
        for i, a in enumerate(outline_assessments, 1):
            name = a.get("name", "Unnamed")
            weight = a.get("weight", "")
            lines.append(f"{i}. **{name}** — {weight}")
        lines.append("")

    if canvas_assignments:
        lines.append("## Canvas Assignments\n")
        for i, a in enumerate(canvas_assignments, 1):
            name = a.get("name", "Unnamed")
            due = format_datetime(a.get("due_at"))
            lines.append(f"{i}. **{name}** — Due: {due}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# MCP Tools - Canvas File Download
# ============================================================================

MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50MB


@mcp.tool(
    name="canvas_download_file",
    annotations={  # type: ignore[arg-type]
        "title": "Download Canvas File to Local",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def canvas_download_file(params: DownloadFileInput) -> str:
    """
    Download a Canvas file to the local filesystem.

    Gets file metadata via Canvas API, then downloads the file content.
    Supports files up to 50MB. After downloading, use Claude's Read tool
    to view PDF content or other file types.

    Args:
        params (DownloadFileInput): Input parameters

    Returns:
        str: Download result with file path and details
    """
    # Get file metadata
    result = await canvas_api_request(f"/files/{params.file_id}")

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    display_name = result.get('display_name', result.get('filename', 'unknown'))
    file_size = result.get('size', 0)
    download_url = result.get('url', '')
    content_type = result.get('content-type', result.get('content_type', ''))

    if not download_url:
        return "Error: No download URL available for this file."

    # Check file size limit
    if file_size > MAX_DOWNLOAD_SIZE:
        size_mb = file_size / (1024 * 1024)
        return f"Error: File too large ({size_mb:.1f}MB). Maximum allowed size is 50MB."

    # Determine save path
    if params.save_path:
        save_path = params.save_path
    else:
        save_path = os.path.join(os.getcwd(), display_name)

    # Create parent directory if needed
    parent_dir = os.path.dirname(save_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Download file with streaming to avoid loading entire file into memory
    client = get_general_client()
    try:
        headers = get_canvas_headers()
        async with client.stream("GET", download_url, headers=headers) as response:
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)

    except httpx.HTTPStatusError as e:
        return f"Error: Download failed (HTTP {e.response.status_code})"
    except httpx.TimeoutException:
        return "Error: Download timed out. The file may be too large."
    except Exception:
        return "Error: Failed to download file."

    size_str = format_file_size(file_size)

    lines = ["# File Downloaded Successfully\n"]
    lines.append(f"- **File**: {display_name}")
    lines.append(f"- **Size**: {size_str}")
    lines.append(f"- **Type**: {content_type}")
    lines.append(f"- **Saved to**: {save_path}")
    lines.append("")
    lines.append("*Use Claude's Read tool to view the file content.*")

    return "\n".join(lines)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
