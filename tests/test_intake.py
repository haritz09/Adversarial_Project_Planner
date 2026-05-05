# test_intake.py
import pytest
from unittest.mock import MagicMock, patch
from agents.intake import intake_node

@patch("agents.intake.get_llm")
def test_intake_full_input(mock_get_llm):
    # Setup mock response for Case 1
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    mock_response = MagicMock()
    mock_response.content = '{"goal": "chat app", "timeline": "3 weeks", "team_size": 2, "constraints": [], "stack": "Firebase", "methodology": null}'
    mock_llm.invoke.return_value = mock_response

    state = {
        "raw_input": "Build a chat app in 3 weeks with 2 devs using Firebase",
        "project_context": None,
        "user_provided_fields": None
    }
    
    # CASE 1: Full input, should not interrupt
    result = intake_node(state)
    
    assert result["project_context"]["goal"] == "chat app"
    assert result["project_context"]["team_size"] == 2
    assert result["user_provided_fields"]["goal"] is True
    assert result["user_provided_fields"]["team_size"] is True

@patch("agents.intake.interrupt")
@patch("agents.intake.get_llm")
def test_intake_missing_input_interruption(mock_get_llm, mock_interrupt):
    # Mock sequence: 
    # 1. First extraction finds missing goal/timeline/team_size
    # 2. User provides answer via interrupt
    # 3. Second extraction finds everything
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm
    
    res1 = MagicMock()
    res1.content = '{"goal": null, "timeline": null, "team_size": null}'
    
    res2 = MagicMock()
    res2.content = '{"goal": "web app", "timeline": "1 month", "team_size": 1}'
    
    mock_llm.invoke.side_effect = [res1, res2]
    mock_interrupt.return_value = "It is a web app for 1 dev in 1 month"

    state = {
        "raw_input": "Help me plan",
        "project_context": None,
        "user_provided_fields": None
    }
    
    result = intake_node(state)
    
    assert mock_interrupt.called
    assert result["project_context"]["goal"] == "web app"
    assert result["user_provided_fields"]["goal"] is True
