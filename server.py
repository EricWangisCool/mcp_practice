import logging
import sys
# pyrefly: ignore [missing-import]
from mcp.server.fastmcp import FastMCP
import os
import json
import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware

# Configure logging to sys.stderr so it doesn't corrupt stdout (which is used for MCP JSON-RPC protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("mcp-practice-server")

# Initialize the FastMCP server
# Listen on 0.0.0.0 for containerized deployment (e.g. AWS ECS)
mcp = FastMCP(
    "mcp-practice-server",
    host=os.environ.get("FASTMCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", 8000)),
    streamable_http_path="/sse"
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


def load_aws_config():
    """
    載入並解析 all_aws_config_exports.json。
    由於 Results 中的每個元素通常是 JSON 字串，此函式會自動將其還原為 Python dict/list。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "all_aws_config_exports.json")
    
    if not os.path.exists(file_path):
        return []
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        raw_results = data.get("Results", [])
        parsed_results = []
        
        for item in raw_results:
            if isinstance(item, str):
                try:
                    parsed_results.append(json.loads(item))
                except json.JSONDecodeError:
                    parsed_results.append({"raw_content": item})
            else:
                parsed_results.append(item)
                
        return parsed_results
    except Exception as e:
        logger.error(f"Error loading AWS Config file: {e}")
        return []


@mcp.tool(name="summary", description="回傳整個 all_aws_config_exports.json 的所有資源清單")
def summary() -> list:
    return load_aws_config()


@mcp.tool(name="list-iam", description="回傳所有與 IAM 相關的資源清單")
def list_iam() -> list:
    resources = load_aws_config()
    # 篩選 resourceType 包含 "IAM" 的資源 (不區分大小寫)
    return [r for r in resources if "iam" in r.get("resourceType", "").lower()]


@mcp.tool(name="list-network", description="回傳所有與網路相關的資源清單，例如 VPC, Subnet, Network Interface (NIC), Security Group (SG), Internet Gateway, Route Table 等")
def list_network() -> list:
    resources = load_aws_config()
    # 網路資源的簡寫前綴
    network_prefixes = {"vpc", "subnet", "eni", "sg", "acl", "rtb", "igw", "eipalloc"}
    
    def is_network(r):
        res_type = r.get("resourceType", "")
        if res_type:
            res_type_lower = res_type.lower()
            if "rds" in res_type_lower:
                return False
                
        res_id = r.get("resourceId", "")
        # 切割 resourceId 並檢查前綴簡寫
        parts = res_id.split("-")
        prefix = parts[0] if parts else ""
        if prefix in network_prefixes:
            return True
        # 檢查任何一段是否包含簡寫（例如 default-vpc-xxx 情況）
        if any(p in network_prefixes for p in parts):
            return True
            
        if res_type:
            res_type_lower = res_type.lower()
            # 支援部分無簡寫 ID 的網路資源，如 LoadBalancer
            if "loadbalancer" in res_type_lower:
                return True
        return False

    return [r for r in resources if is_network(r)]


@mcp.tool(name="list-storage", description="回傳所有與儲存相關的資源清單，例如 EBS Volume, S3 Bucket, EFS FileSystem 等")
def list_storage() -> list:
    resources = load_aws_config()
    # EBS Volume 的簡寫為 vol，Snapshot 為 snap
    storage_prefixes = {"vol", "snap"}
    
    def is_storage(r):
        res_id = r.get("resourceId", "")
        parts = res_id.split("-")
        prefix = parts[0] if parts else ""
        if prefix in storage_prefixes:
            return True
            
        res_type = r.get("resourceType", "")
        if res_type:
            res_type_lower = res_type.lower()
            # 匹配 s3 bucket 與 efs filesystem
            if any(kw in res_type_lower for kw in ["s3::bucket", "efs::filesystem", "efs::accesspoint"]):
                return True
        return False

    return [r for r in resources if is_storage(r)]


@mcp.tool(name="list-compute", description="回傳所有與運算相關的資源清單，例如 EC2 Instance, Lambda Function, ECS Cluster/Service/TaskDefinition 等")
def list_compute() -> list:
    resources = load_aws_config()
    
    def is_compute(r):
        res_id = r.get("resourceId", "")
        parts = res_id.split("-")
        prefix = parts[0] if parts else ""
        # EC2 Instance 的簡寫前綴為 i
        if prefix == "i":
            return True
            
        res_type = r.get("resourceType", "")
        if res_type:
            res_type_lower = res_type.lower()
            if any(kw in res_type_lower for kw in ["lambda", "ecs::", "eks::"]):
                return True
        return False

    return [r for r in resources if is_compute(r)]


@mcp.tool(name="list-all-types", description="列出目前資料檔案中存在的所有資源類型 (ResourceType)")
def list_all_types() -> list:
    resources = load_aws_config()
    types = set(r.get("resourceType") for r in resources if r.get("resourceType"))
    return sorted(list(types))


@mcp.tool(name="query-by-type", description="依據指定的資源類型（例如 AWS::EC2::Subnet）過濾並回傳資源列表")
def query_by_type(resource_type: str) -> list:
    resources = load_aws_config()
    return [r for r in resources if r.get("resourceType") == resource_type]


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        logger.info(f"\n[DEBUG REQUEST] {request.method} {request.url}")
        logger.info(f"Headers: {dict(request.headers)}")
        try:
            body = await request.body()
            if body:
                logger.info(f"Body: {body.decode('utf-8', errors='ignore')}")
        except Exception as e:
            logger.error(f"Error reading body: {e}")
        
        response = await call_next(request)
        logger.info(f"[DEBUG RESPONSE] Status: {response.status_code}\n")
        return response


class SSEHeartbeatMiddleware:
    """
    ASGI middleware to send keep-alive heartbeats (: comments)
    every 10 seconds on the SSE GET connection.
    """
    def __init__(self, app, path="/sse", interval=10):
        self.app = app
        self.path = path
        self.interval = interval

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "GET" and scope["path"] == self.path:
            import asyncio
            send_lock = asyncio.Lock()
            active = True
            response_started = False

            async def locked_send(message):
                async with send_lock:
                    await send(message)

            async def heartbeat_sender():
                while active:
                    await asyncio.sleep(self.interval)
                    if not active:
                        break
                    if not response_started:
                        continue
                    try:
                        logger.info("Sending SSE keep-alive heartbeat comment (:\\n\\n)")
                        await locked_send({
                            "type": "http.response.body",
                            "body": b":\n\n",
                            "more_body": True
                        })
                    except Exception as e:
                        logger.warning(f"Failed to send SSE heartbeat: {e}")
                        break

            async def wrapped_send(message):
                nonlocal active, response_started
                if message["type"] == "http.response.start":
                    response_started = True
                elif message["type"] == "http.response.body" and not message.get("more_body", False):
                    active = False
                await locked_send(message)

            heartbeat_task = asyncio.create_task(heartbeat_sender())
            try:
                await self.app(scope, receive, wrapped_send)
            finally:
                active = False
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
        else:
            await self.app(scope, receive, send)


if __name__ == "__main__":
    import os
    # Check if we should run in SSE mode (standard for ECS/Web deployments)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    
    if transport == "sse":
        logger.info(f"Starting FastMCP server via SSE (listening on {mcp.settings.host}:{mcp.settings.port})")
        app = mcp.streamable_http_app()
        app.add_middleware(RequestLoggerMiddleware)
        
        # Wrap with SSEHeartbeatMiddleware to keep the connection alive
        heartbeat_app = SSEHeartbeatMiddleware(
            app,
            path=mcp.settings.streamable_http_path,
            interval=10
        )
        
        uvicorn.run(heartbeat_app, host=mcp.settings.host, port=mcp.settings.port)
    else:
        logger.info("Starting FastMCP server via stdio")
        mcp.run(transport="stdio")

