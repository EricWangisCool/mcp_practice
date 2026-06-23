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

# Initialize the FastMCP server
mcp = FastMCP("mcp-practice-server")

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


@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """
    Retrieve a custom greeting resource for a user.
    
    Args:
        name: The username to greet.
    """
    logger.info(f"Resource requested: greeting for {name}")
    return f"Hello, {name}! Welcome to the Model Context Protocol (MCP) server."

if __name__ == "__main__":
    # Start the server (runs via stdio transport by default)
    mcp.run()
