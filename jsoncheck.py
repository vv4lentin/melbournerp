import discord
from discord.ext import commands
import json
import os
from collections import OrderedDict  # For detecting duplicate keys
import io
import re

class JsonCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Define max file size (e.g., 8MB for Discord free tier)
        self.max_file_size = 8 * 1024 * 1024  # 8MB in bytes

    @commands.command(name='jsoncheck')
    async def json_check(self, ctx, filename: str = None):
        # Step 1: Retrieve JSON content
        json_content, source_name, source_type = await self._get_json_content(ctx, filename)
        if json_content is None:
            return  # Error message already sent

        # Step 2: Validate JSON
        try:
            # Parse with duplicate key detection
            json_data = json.loads(json_content, object_pairs_hook=self._detect_duplicate_keys)
            await ctx.send(
                f"✅ Success: The JSON from '{source_name}' is valid.\n"
                f"- Type: {'Object' if isinstance(json_data, dict) else 'Array' if isinstance(json_data, list) else type(json_data).__name__}\n"
                f"- Size: {len(json_content)} bytes"
            )

        except json.JSONDecodeError as e:
            # Detailed error message construction
            error_details = await self._construct_detailed_error(ctx, json_content, e, source_name)
            await ctx.send(error_details)
        
        except ValueError as e:
            # Handle duplicate keys or other ValueError cases
            await ctx.send(
                f"❌ Error in '{source_name}': {str(e)}\n"
                f"- **Suggestion**: Ensure object keys are unique. JSON does not allow duplicate keys in the same object."
            )
        
        except UnicodeDecodeError as e:
            await ctx.send(
                f"❌ Encoding Error in '{source_name}': Invalid UTF-8 encoding.\n"
                f"- **Details**: {str(e)}\n"
                f"- **Suggestion**: Ensure the file uses UTF-8 encoding. Check for invalid characters or save the file with UTF-8 encoding in your editor."
            )
        
        except Exception as e:
            await ctx.send(
                f"❌ Unexpected Error in '{source_name}': {str(e)}\n"
                f"- **Suggestion**: Check file permissions, content, or contact the bot developer."
            )

    async def _get_json_content(self, ctx, filename):
        """Retrieve JSON content from a file or attachment."""
        if filename:
            # Local file mode
            if not filename.endswith('.json'):
                await ctx.send("❌ Error: Please provide a file with a .json extension.")
                return None, None, None
            if not os.path.isfile(filename):
                await ctx.send(f"❌ Error: File '{filename}' not found on the bot's server.")
                return None, None, None
            if os.path.getsize(filename) > self.max_file_size:
                await ctx.send(f"❌ Error: File '{filename}' exceeds size limit ({self.max_file_size // 1024 // 1024}MB).")
                return None, None, None
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    return file.read(), filename, 'local file'
            except UnicodeDecodeError:
                raise UnicodeDecodeError("Invalid UTF-8 encoding", b"", 0, 0, "File is not valid UTF-8")
        
        else:
            # Attachment mode
            if not ctx.message.attachments:
                await ctx.send("❌ Error: No filename provided and no attachments found. Upload a JSON file or specify a server file.")
                return None, None, None
            attachment = next((att for att in ctx.message.attachments if att.filename.endswith('.json')), None)
            if not attachment:
                await ctx.send("❌ Error: No JSON attachment found. Please upload a file with a .json extension.")
                return None, None, None
            if attachment.size > self.max_file_size:
                await ctx.send(f"❌ Error: Attachment '{attachment.filename}' exceeds size limit ({self.max_file_size // 1024 // 1024}MB).")
                return None, None, None
            content = await attachment.read()
            try:
                return content.decode('utf-8'), attachment.filename, 'attachment'
            except UnicodeDecodeError:
                raise UnicodeDecodeError("Invalid UTF-8 encoding", b"", 0, 0, "Attachment is not valid UTF-8")

    def _detect_duplicate_keys(self, pairs):
        """Detect duplicate keys in JSON objects."""
        result = OrderedDict()
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate key detected: '{key}'")
            result[key] = value
        return result

    async def _construct_detailed_error(self, ctx, json_content, error, source_name):
        """Construct a detailed error message for JSONDecodeError."""
        error_msg = str(error)
        line_num = getattr(error, 'lineno', 1)
        col_num = getattr(error, 'colno', 1)
        error_pos = getattr(error, 'pos', 0)

        # Split content into lines for context
        lines = json_content.splitlines()
        if not lines:
            return (
                f"❌ Error in '{source_name}': Empty JSON file.\n"
                f"- **Details**: {error_msg}\n"
                f"- **Suggestion**: Ensure the file contains valid JSON (e.g., {{}} or [])."
            )

        # Extract context (up to 3 lines around the error)
        start_line = max(0, line_num - 2)  # 1-based to 0-based, show 1 line before
        end_line = min(len(lines), line_num + 1)  # Show 1 line after
        context_lines = lines[start_line:end_line]
        context = "\n".join(f"{i+1}: {line}" for i, line in enumerate(context_lines, start_line + 1))

        # Highlight the error position
        if line_num <= len(lines):
            error_line = lines[line_num - 1]
            pointer = " " * (col_num - 1) + "^"
            context += f"\n{line_num}: {error_line}\n   {pointer}"

        # Analyze error type and provide specific suggestions
        suggestion = self._get_error_suggestion(error_msg, json_content, error_pos)

        # Build the detailed error message
        return (
            f"❌ Error in '{source_name}' at line {line_num}, column {col_num}:\n"
            f"```json\n{context}\n```\n"
            f"- **Error Type**: {self._classify_error(error_msg)}\n"
            f"- **Details**: {error_msg}\n"
            f"- **Suggestion**: {suggestion}"
        )

    def _classify_error(self, error_msg):
        """Classify the type of JSON error."""
        error_msg = error_msg.lower()
        if "expecting" in error_msg:
            return "Syntax Error (Missing or misplaced character)"
        if "unterminated" in error_msg:
            return "Unterminated Structure (e.g., missing brace/bracket)"
        if "invalid control character" in error_msg:
            return "Invalid Character (e.g., unescaped control character)"
        if "extra data" in error_msg:
            return "Extra Data (Content after valid JSON)"
        if "invalid escape" in error_msg:
            return "Invalid Escape Sequence"
        return "Generic JSON Error"

    def _get_error_suggestion(self, error_msg, json_content, error_pos):
        """Provide tailored suggestions for JSON errors."""
        error_msg = error_msg.lower()
        if "expecting ','" in error_msg:
            return "A comma is missing between elements. Check arrays or objects for missing commas (e.g., [1, 2, 3] or {'a': 1, 'b': 2})."
        if "expecting ':'" in error_msg:
            return "A colon is missing in an object key-value pair. Ensure objects use 'key': value syntax (e.g., {'key': 'value'})."
        if "expecting property name" in error_msg:
            return "Object keys must be strings in quotes. Ensure keys are quoted (e.g., {'key': 1} instead of {key: 1})."
        if "unterminated" in error_msg:
            return "Check for unbalanced brackets or braces. Ensure every { has a } and every [ has a ]."
        if "invalid control character" in error_msg:
            return "Remove or escape special characters (e.g., \\n, \\t). Use double backslashes for escapes (e.g., '\\\\n')."
        if "extra data" in error_msg:
            return "JSON must be a single object or array. Remove extra content after the main JSON structure."
        if "invalid escape" in error_msg:
            return "Check for invalid escape sequences in strings. Use valid escapes like \\n, \\t, or \\uXXXX."
        if "expecting value" in error_msg:
            return "A value is missing or invalid. Ensure all keys have values and use valid JSON types (e.g., strings, numbers, objects, arrays, true, false, null)."
        
        # Fallback: Try to guess based on context
        try:
            snippet = json_content[max(0, error_pos - 10):error_pos + 10]
            if '{' in snippet and '}' not in snippet:
                return "Possibly missing a closing brace (}). Check object boundaries."
            if '[' in snippet and ']' not in snippet:
                return "Possibly missing a closing bracket (]). Check array boundaries."
            if '"' in snippet and snippet.count('"') % 2 != 0:
                return "Possibly missing a closing quote (\") in a string."
        except:
            pass
        return "Review the JSON syntax at the specified line/column. Compare against JSON spec (json.org) or use a JSON linter."

async def setup(bot):
    await bot.add_cog(JsonCheck(bot))
