#!/usr/bin/env python3

from IPython.display import Image, display
from langchain_core.runnables.graph import MermaidDrawMethod
import os

# Import the workflow app from agent_eval.py
from src.agent_eval import app

def main():
    # Create a directory for saving the image if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Generate the mermaid png image
    image_data = app.get_graph().draw_mermaid_png(
        draw_method=MermaidDrawMethod.API,
    )
    
    # Save the image to a file
    output_path = "output/agent_graph.png"
    with open(output_path, "wb") as f:
        f.write(image_data)
    
    print(f"Graph image saved to {output_path}")
    
    # For Jupyter notebooks/IPython, you could also display it:
    # display(Image(image_data))

if __name__ == "__main__":
    main() 