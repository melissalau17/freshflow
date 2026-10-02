"""FreshFlow custom components for use with `lfx serve` (Render) or local Langflow.

How to use:
  1. Set the env var FRESHFLOW_HOME to the absolute path of this project folder BEFORE running `langflow run`
     (e.g.  export FRESHFLOW_HOME=/path/to/freshflow).
  2. In the Langflow canvas: New Custom Component -> paste ONE class below -> Save.
  3. Turn on "Tool Mode" for the component and connect it to the Agent's Tools input.
Each class below is a separate component; paste them one at a time.

Imports use lfx.* paths (compatible with both `lfx serve` and full Langflow installs >= 1.12).
"""
import os
import sys

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

_home = os.environ.get("FRESHFLOW_HOME", "")
if _home and _home not in sys.path:
    sys.path.insert(0, _home)

from src.tools_api import optimize_dispatch_tool, score_spoilage_tool  # noqa: E402


class SpoilageRiskTool(Component):
    display_name = "FreshFlow Spoilage Risk"
    description = "Scores spoilage urgency for one harvest lot (rule-based)."
    icon = "leaf"
    name = "FreshFlowSpoilageRisk"

    inputs = [
        MessageTextInput(name="commodity", display_name="Commodity", info="e.g. tomato", tool_mode=True),
        MessageTextInput(name="hours_since_harvest", display_name="Hours since harvest", tool_mode=True),
        MessageTextInput(name="estimated_transit_hours", display_name="Estimated transit hours", tool_mode=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="run")]

    def run(self) -> Data:
        out = score_spoilage_tool(self.commodity, self.hours_since_harvest, self.estimated_transit_hours)
        return Data(data=out)


class DispatchOptimizerTool(Component):
    display_name = "FreshFlow Dispatch Optimizer"
    description = ("Recommends vehicle assignment and pickup order, compared with a distance-only baseline. "
                   "Pass harvests and vehicles as JSON strings; leave empty to use the demo scenario.")
    icon = "truck"
    name = "FreshFlowDispatchOptimizer"

    inputs = [
        MessageTextInput(name="harvests_json", display_name="Harvests JSON", tool_mode=True),
        MessageTextInput(name="vehicles_json", display_name="Vehicles JSON", tool_mode=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="run")]

    def run(self) -> Data:
        return Data(data=optimize_dispatch_tool(self.harvests_json or "", self.vehicles_json or ""))
