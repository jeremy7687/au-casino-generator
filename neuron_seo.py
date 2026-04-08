#!/usr/bin/env python3
"""
NeuronWriter API wrapper stub.

Returns empty data when NEURONWRITER_API_KEY is not set.
Replace this with a full implementation once you have a NeuronWriter account
and set the environment variable.

Required env vars (when implementing):
    NEURONWRITER_API_KEY   — from app.neuronwriter.com
    NEURONWRITER_PROJECT   — project ID from NeuronWriter
"""
import os


def get_neuron_recommendations(keyword: str) -> dict:
    """
    Fetch NeuronWriter SEO recommendations for a keyword.
    Returns an empty-but-valid structure when API key is not configured.
    """
    api_key = os.environ.get("NEURONWRITER_API_KEY", "")
    if not api_key:
        print(f"   ⚠️   NEURONWRITER_API_KEY not set — skipping NeuronWriter for: {keyword}")
        return {
            "questions_paa": [],
            "questions_suggest": [],
            "questions_content": [],
            "h2_terms": [],
            "entities": [],
            "competitors": [],
            "content_terms": [],
        }

    # TODO: Implement real NeuronWriter API call
    # Reference: https://app.neuronwriter.com/api-docs
    project_id = os.environ.get("NEURONWRITER_PROJECT", "")
    print(f"   ⚠️   NeuronWriter full implementation pending (project: {project_id})")
    return {
        "questions_paa": [],
        "questions_suggest": [],
        "questions_content": [],
        "h2_terms": [],
        "entities": [],
        "competitors": [],
        "content_terms": [],
    }
