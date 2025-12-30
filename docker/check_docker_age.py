#!/usr/bin/env python3
import subprocess
import datetime
import sys
import os

def get_docker_image_age(image_name):
    """Get the creation time of a Docker image in epoch format"""
    try:
        result = subprocess.run(
            ['docker', 'inspect', '--format={{.Created}}', image_name],
            capture_output=True,
            text=True,
            check=True
        )
        timestamp_str = result.stdout.strip()
        # Parse RFC 3339 timestamp
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except subprocess.CalledProcessError as e:
        print(f"Error inspecting Docker image: {e}")
        return None

def rebuild_docker_image(dockerfile_path=".", image_name="r2agent:dev"):
    """Rebuild the Docker image"""
    try:
        print(f"Rebuilding Docker image {image_name}...")
        # Build from project root but specify Dockerfile location
        result = subprocess.run(
            ['docker', 'build', '-f', 'docker/Dockerfile', '-t', image_name, dockerfile_path],
            check=True
        )
        print("Docker image rebuilt successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error rebuilding Docker image: {e}")
        return False

def main():
    image_name = "r2agent:dev"
    # Build from project root since Dockerfile references files with relative paths
    dockerfile_path = "."

    # Get image creation time
    created_epoch = get_docker_image_age(image_name)
    if created_epoch is None:
        sys.exit(1)

    # Get current time
    current_epoch = int(datetime.datetime.now().timestamp())

    # Calculate age in days
    age_seconds = current_epoch - created_epoch
    age_days = age_seconds / (24 * 3600)

    print(f"Docker image '{image_name}' is {age_days:.2f} days old")

    # Check if older than 5 days
    if age_days > 5:
        print("Image is older than 5 days. Rebuilding...")
        success = rebuild_docker_image(dockerfile_path, image_name)
        if not success:
            sys.exit(1)
    else:
        print("Image is still fresh (≤5 days old). No rebuild needed.")

if __name__ == "__main__":
    main()
