"""Unit tests for the structure-aware chunker."""

import pytest
from app.ingestion.parser import Block, ParsedDoc
from app.ingestion.chunker import chunk_document


def test_empty_document():
    doc = ParsedDoc(blocks=[], page_count=0)
    chunks = chunk_document(doc)
    assert chunks == []


def test_single_short_section():
    blocks = [
        Block(page=1, text="Introduction to Physics", is_heading=True),
        Block(page=1, text="Physics is the natural science of matter, its fundamental constituents, its motion and behavior through space and time, and the related entities of energy and force. It is one of the most fundamental scientific disciplines.", is_heading=False),
    ]
    doc = ParsedDoc(blocks=blocks, page_count=1)
    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].section_path == "Introduction to Physics"
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert "Physics is the natural science" in chunks[0].content


def test_heading_forces_split():
    # Even if content is short, a new heading forces previous section to flush
    blocks = [
        Block(page=1, text="Chapter 1: Kinematics", is_heading=True),
        Block(page=1, text="Kinematics describes the motion of points, bodies, and systems of bodies without considering the forces that cause them to move. It is widely used in astrophysics and robotics.", is_heading=False),
        Block(page=2, text="Chapter 2: Dynamics", is_heading=True),
        Block(page=2, text="Dynamics deals with the effect that forces have on the motion of objects. Isaac Newton laid down the foundational laws governing the relationship between force and acceleration.", is_heading=False),
    ]
    doc = ParsedDoc(blocks=blocks, page_count=2)
    chunks = chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].section_path == "Chapter 1: Kinematics"
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert "Kinematics describes" in chunks[0].content

    assert chunks[1].section_path == "Chapter 2: Dynamics"
    assert chunks[1].page_start == 2
    assert chunks[1].page_end == 2
    assert "Dynamics deals with" in chunks[1].content


def test_chunk_word_overflow_and_overlap():
    # Generate 600 words to force a chunk split (threshold is 500 words)
    words = ["word" + str(i) for i in range(600)]
    long_para = " ".join(words)

    blocks = [
        Block(page=1, text="Large Section", is_heading=True),
        Block(page=1, text=long_para[:1500], is_heading=False),
        Block(page=2, text=long_para[1500:], is_heading=False),
    ]
    doc = ParsedDoc(blocks=blocks, page_count=2)
    chunks = chunk_document(doc)

    assert len(chunks) >= 2
    assert chunks[0].section_path == "Large Section"
    assert chunks[1].section_path == "Large Section"


def test_tiny_fragments_filtered():
    # Paragraph with fewer than 15 words should be filtered out
    blocks = [
        Block(page=1, text="Tiny Section", is_heading=True),
        Block(page=1, text="Too short fragment.", is_heading=False),
    ]
    doc = ParsedDoc(blocks=blocks, page_count=1)
    chunks = chunk_document(doc)
    assert len(chunks) == 0
