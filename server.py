import logging
import sys
# pyrefly: ignore [missing-import]
from mcp.server.fastmcp import FastMCP

# Configure logging to sys.stderr so it doesn't corrupt stdout (which is used for MCP JSON-RPC protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("mcp-practice-server")

import os

# Initialize the FastMCP server
# Listen on 0.0.0.0 for containerized deployment (e.g. AWS ECS)
mcp = FastMCP(
    "mcp-practice-server",
    host=os.environ.get("FASTMCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", 8000))
)

@mcp.tool()
def add(a: float, b: float) -> float:
    """
    Add two numbers together.
    
    Args:
        a: The first number.
        b: The second number.
    """
    logger.info(f"Tool called: add({a}, {b})")
    return a + b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """
    Multiply two numbers together.
    
    Args:
        a: The first number.
        b: The second number.
    """
    logger.info(f"Tool called: multiply({a}, {b})")
    return a * b

@mcp.tool()
def aws_s3_ls(path: str = "") -> str:
    """
    List S3 buckets or objects under a path, mimicking the 'aws s3 ls' command.
    
    Args:
        path: Optional path to list. If empty, lists all buckets.
              Can be in 's3://bucket-name/prefix/' format or just 'bucket-name/prefix/'.
    """
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    
    logger.info(f"Tool called: aws_s3_ls(path='{path}')")
    try:
        s3 = boto3.client('s3')
        
        # Clean path
        path = path.strip()
        if path.startswith("s3://"):
            path = path[5:]
            
        # If path is empty, list all buckets
        if not path or path == "/":
            response = s3.list_buckets()
            buckets = response.get("Buckets", [])
            if not buckets:
                return "No buckets found."
            lines = []
            for b in buckets:
                creation_date = b["CreationDate"].strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"{creation_date} {b['Name']}")
            return "\n".join(lines)
            
        # Otherwise, parse bucket and prefix
        parts = path.split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        
        # List objects under the bucket and prefix
        # Use Delimiter='/' to distinguish between folders (CommonPrefixes) and files (Contents)
        params = {"Bucket": bucket_name}
        if prefix:
            params["Prefix"] = prefix
        params["Delimiter"] = "/"
        
        response = s3.list_objects_v2(**params)
        
        lines = []
        
        # Add subfolders (CommonPrefixes)
        folders = response.get("CommonPrefixes", [])
        for f in folders:
            # CommonPrefixes contains 'Prefix' like 'folder/subfolder/'
            # We want to display relative name or folder prefix
            lines.append(f"                           PRE {f['Prefix'].split('/')[-2]}/")
            
        # Add files (Contents)
        objects = response.get("Contents", [])
        for obj in objects:
            key = obj["Key"]
            base_name = key.split("/")[-1]
            if not base_name and key == prefix:
                continue
            last_modified = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S")
            size = obj["Size"]
            lines.append(f"{last_modified} {size:>10} {base_name if base_name else key}")
            
        if not lines:
            return f"No objects or folders found under s3://{bucket_name}/{prefix}"
            
        return "\n".join(lines)
        
    except (BotoCoreError, ClientError) as e:
        logger.error(f"AWS Error: {str(e)}")
        return f"Error connecting to AWS S3: {str(e)}\nPlease verify your AWS credentials (e.g. run 'aws configure' or set environment variables in your config)."
    except Exception as e:
        logger.error(f"Unexpected Error: {str(e)}")
        return f"An unexpected error occurred: {str(e)}"



@mcp.tool()
def aws_cw_logs_list_groups(prefix: str = "", limit: int = 20) -> str:
    """
    List CloudWatch Log Groups.
    
    Args:
        prefix: Optional prefix to filter log groups by name.
        limit: Maximum number of log groups to return (default 20, max 50).
    """
    import boto3
    import time
    from botocore.exceptions import BotoCoreError, ClientError
    
    logger.info(f"Tool called: aws_cw_logs_list_groups(prefix='{prefix}', limit={limit})")
    try:
        logs = boto3.client('logs')
        params = {"limit": min(limit, 50)}
        if prefix:
            params["logGroupNamePrefix"] = prefix
            
        response = logs.describe_log_groups(**params)
        groups = response.get("logGroups", [])
        
        if not groups:
            return "No log groups found."
            
        lines = []
        for g in groups:
            creation_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(g.get("creationTime", 0) / 1000.0))
            lines.append(f"{creation_time} | {g['logGroupName']}")
        return "\n".join(lines)
    except (BotoCoreError, ClientError) as e:
        logger.error(f"AWS Error in list_groups: {str(e)}")
        return f"Error connecting to AWS CloudWatch Logs: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected Error in list_groups: {str(e)}")
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def aws_cw_logs_get_events(log_group: str, log_stream: str = "", limit: int = 50) -> str:
    """
    Retrieve log events from a CloudWatch Log Group.
    If no log_stream is specified, it will automatically fetch events from the most recently active log stream in that group.
    
    Args:
        log_group: The name of the log group.
        log_stream: Optional log stream name. If omitted, the latest stream is used.
        limit: Number of events to return (default 50, max 100).
    """
    import boto3
    import time
    from botocore.exceptions import BotoCoreError, ClientError
    
    logger.info(f"Tool called: aws_cw_logs_get_events(log_group='{log_group}', log_stream='{log_stream}', limit={limit})")
    try:
        logs = boto3.client('logs')
        
        target_stream = log_stream
        if not target_stream:
            # Find the most recently active log stream
            response = logs.describe_log_streams(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                limit=1
            )
            streams = response.get("logStreams", [])
            if not streams:
                return f"No log streams found in log group '{log_group}'."
            target_stream = streams[0]["logStreamName"]
            logger.info(f"Automatically selected latest log stream: {target_stream}")
            
        # Get log events
        response = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=target_stream,
            limit=min(limit, 100),
            startFromHead=False  # Get latest logs from the tail
        )
        events = response.get("events", [])
        if not events:
            return f"No events found in log stream '{target_stream}' of group '{log_group}'."
            
        lines = []
        if not log_stream:
            lines.append(f"--- Showing logs from automatically selected latest stream: {target_stream} ---")
        else:
            lines.append(f"--- Showing logs from stream: {target_stream} ---")
            
        for event in events:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event['timestamp'] / 1000.0))
            message = event['message'].rstrip('\r\n')
            lines.append(f"[{timestamp}] {message}")
            
        return "\n".join(lines)
    except (BotoCoreError, ClientError) as e:
        logger.error(f"AWS Error in get_events: {str(e)}")
        return f"Error retrieving logs from AWS CloudWatch: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected Error in get_events: {str(e)}")
        return f"An unexpected error occurred: {str(e)}"


@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """
    Retrieve a custom greeting resource for a user.
    
    Args:
        name: The username to greet.
    """
    logger.info(f"Resource requested: greeting for {name}")
    return f"Hello, {name}! Welcome to the Model Context Protocol (MCP) server."


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """
    Health check endpoint for ALB/ECS Target Group.
    """
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "healthy", "service": "mcp-practice-server"})


if __name__ == "__main__":
    import os
    # Check if we should run in SSE mode (standard for ECS/Web deployments)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    
    if transport == "sse":
        logger.info(f"Starting FastMCP server via SSE (listening on {mcp.settings.host}:{mcp.settings.port})")
        mcp.run(transport="sse")
    else:
        logger.info("Starting FastMCP server via stdio")
        mcp.run(transport="stdio")
