#!/usr/bin/env python3
"""Populate openai-to-sqlite-compatible embeddings using OpenRouter."""

import argparse
import os
import sqlite3
import struct
import sys
import time

import httpx

DEFAULT_MODEL = "openai/text-embedding-3-small"
DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/embeddings"
EXPECTED_DIMENSIONS = 1536
DEFAULT_MAX_INPUT_CHARS = 8000


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate OpenRouter embeddings for TIL records and store them in the "
            "BLOB format expected by openai-to-sqlite 0.4.x."
        )
    )
    parser.add_argument("database", nargs="?", default="tils.db")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument(
        "--max-input-chars",
        type=int,
        default=DEFAULT_MAX_INPUT_CHARS,
        help="Truncate each document to this many characters (default: 8000)",
    )
    parser.add_argument("--rebuild", action="store_true", help="Drop embeddings and similarities first")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    return parser.parse_args()


def request_embeddings(client, endpoint, headers, model, texts, attempts=5):
    for attempt in range(attempts):
        response = client.post(
            endpoint,
            headers=headers,
            json={"model": model, "input": texts},
        )
        if response.status_code not in (429, 500, 502, 503, 504):
            if response.is_error:
                raise RuntimeError(
                    f"OpenRouter returned {response.status_code}: {response.text}"
                )
            return response.json()
        if attempt == attempts - 1:
            response.raise_for_status()
        delay = 2**attempt
        print(f"OpenRouter returned {response.status_code}; retrying in {delay}s", file=sys.stderr)
        time.sleep(delay)
    raise AssertionError("unreachable")


def chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def main():
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")
    if args.max_input_chars < 1:
        raise SystemExit("--max-input-chars must be at least 1")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY before running this script")

    conn = sqlite3.connect(args.database)
    try:
        if args.rebuild:
            conn.execute("drop table if exists similarities")
            conn.execute("drop table if exists embeddings")
            conn.commit()

        if not conn.execute(
            "select 1 from sqlite_master where type = 'table' and name = 'til'"
        ).fetchone():
            raise SystemExit(f"{args.database} does not contain a til table")

        conn.execute(
            "create table if not exists embeddings ("
            "id text primary key, embedding blob)"
        )
        conn.commit()

        rows = conn.execute(
            "select path, title, topic, body from til "
            "where path not in (select id from embeddings) order by path"
        ).fetchall()
        if not rows:
            print("All TIL records already have embeddings")
            return

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if os.environ.get("OPENROUTER_HTTP_REFERER"):
            headers["HTTP-Referer"] = os.environ["OPENROUTER_HTTP_REFERER"]
        if os.environ.get("OPENROUTER_APP_NAME"):
            headers["X-Title"] = os.environ["OPENROUTER_APP_NAME"]

        completed = 0
        total_tokens = 0
        with httpx.Client(timeout=120) as client:
            for batch in chunks(rows, args.batch_size):
                ids = [row[0] for row in batch]
                full_texts = [" ".join(value or "" for value in row[1:]) for row in batch]
                texts = [text[: args.max_input_chars] for text in full_texts]
                truncated = sum(
                    len(text) > args.max_input_chars for text in full_texts
                )
                if truncated:
                    print(
                        f"Truncated {truncated} inputs in this batch to "
                        f"{args.max_input_chars} characters",
                        file=sys.stderr,
                    )
                payload = request_embeddings(
                    client, args.endpoint, headers, args.model, texts
                )
                results = sorted(payload["data"], key=lambda item: item["index"])
                if len(results) != len(batch):
                    raise RuntimeError(
                        f"OpenRouter returned {len(results)} embeddings for {len(batch)} inputs"
                    )

                inserts = []
                for expected_index, result in enumerate(results):
                    if result["index"] != expected_index:
                        raise RuntimeError("OpenRouter returned unexpected embedding indexes")
                    vector = result["embedding"]
                    if len(vector) != EXPECTED_DIMENSIONS:
                        raise RuntimeError(
                            f"Model {args.model} returned {len(vector)} dimensions; "
                            f"openai-to-sqlite 0.4.x requires {EXPECTED_DIMENSIONS}"
                        )
                    blob = struct.pack("f" * EXPECTED_DIMENSIONS, *vector)
                    inserts.append((ids[expected_index], blob))

                with conn:
                    conn.executemany(
                        "insert or replace into embeddings (id, embedding) values (?, ?)",
                        inserts,
                    )
                completed += len(batch)
                total_tokens += payload.get("usage", {}).get("total_tokens", 0)
                print(f"Embedded {completed}/{len(rows)} records", file=sys.stderr)

        print(
            f"Stored {completed} embeddings using {args.model}"
            + (f" ({total_tokens} tokens)" if total_tokens else "")
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
