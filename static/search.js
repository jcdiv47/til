/* Search-as-you-type, layered on top of the /tils/search canned query.
   Without JS the form still submits and Datasette renders the same results
   server-side, so this file is pure enhancement. */
(function () {
    var form = document.querySelector("form.search");
    var results = document.getElementById("search-results");
    if (!form || !results || !window.fetch) {
        return;
    }
    var input = form.querySelector("input[type=search]");
    var browse = document.getElementById("browse");
    var DEBOUNCE_MS = 130;

    var timer = null;
    var controller = null;
    var initialQ = new URLSearchParams(location.search).get("q") || "";
    // Whatever is on screen right now, so we never refetch it. The search page
    // arrives with results already rendered; the home page never does.
    var serverRendered = !!results.innerHTML.trim();
    var rendered = serverRendered ? initialQ : "";

    function esc(s) {
        return String(s).replace(/[&<>"]/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
        });
    }

    // The canned query wraps matched terms in these sentinels — same trick the
    // highlight() template function uses, applied after escaping.
    function snippet(s) {
        return esc(s || "")
            .replace(/b4de2a49c8/g, "<strong>")
            .replace(/8c94a2ed4b/g, "</strong>");
    }

    function render(q, rows) {
        if (!q) {
            results.innerHTML = "";
            results.hidden = true;
            if (browse) {
                browse.hidden = false;
            }
            return;
        }
        var html =
            '<p class="result-count">' +
            rows.length +
            (rows.length === 1 ? " match" : " matches") +
            " for &ldquo;" +
            esc(q) +
            "&rdquo;</p>";
        if (!rows.length) {
            html +=
                '<p class="no-results">Nothing here matches that. Try a single' +
                ' word, or <a href="/all">browse the register</a>.</p>';
        }
        html += '<div class="results">';
        rows.forEach(function (til) {
            html +=
                '<article class="result"><h2><a href="/' +
                esc(til.topic) +
                "/" +
                esc(til.slug) +
                '">' +
                esc(til.title) +
                '</a></h2><p class="search-snippet">' +
                snippet(til.snippet) +
                '</p><p class="entry-meta"><a href="/' +
                esc(til.topic) +
                '">' +
                esc(til.topic) +
                "</a> &middot; <time>" +
                esc((til.created || "").slice(0, 10)) +
                "</time></p></article>";
        });
        html += "</div>";
        results.innerHTML = html;
        results.hidden = false;
        if (browse) {
            browse.hidden = true;
        }
    }

    function search(q) {
        if (q === rendered) {
            return;
        }
        if (controller) {
            controller.abort();
        }
        history.replaceState(
            null,
            "",
            location.pathname + (q ? "?q=" + encodeURIComponent(q) : "")
        );
        if (!q) {
            rendered = "";
            results.classList.remove("is-searching");
            render("", []);
            return;
        }
        controller = new AbortController();
        results.classList.add("is-searching");
        fetch("/tils/search.json?_shape=array&q=" + encodeURIComponent(q), {
            signal: controller.signal,
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("search failed: " + response.status);
                }
                return response.json();
            })
            .then(function (rows) {
                rendered = q;
                results.classList.remove("is-searching");
                render(q, rows);
            })
            .catch(function (error) {
                if (error.name !== "AbortError") {
                    // Leave the last good results up; the form still submits.
                    results.classList.remove("is-searching");
                }
            });
    }

    input.addEventListener("input", function () {
        var q = input.value.trim();
        clearTimeout(timer);
        timer = setTimeout(function () {
            search(q);
        }, DEBOUNCE_MS);
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && input.value) {
            event.preventDefault();
            input.value = "";
            clearTimeout(timer);
            search("");
        }
    });

    // Enter would reload the page we are already showing.
    form.addEventListener("submit", function (event) {
        var q = input.value.trim();
        if (q === rendered) {
            event.preventDefault();
            input.blur();
        }
    });

    // Landing on /?q=... (or hitting back) should show those results.
    window.addEventListener("popstate", function () {
        var q = new URLSearchParams(location.search).get("q") || "";
        input.value = q;
        search(q);
    });

    if (initialQ && !serverRendered) {
        input.value = initialQ;
        search(initialQ);
    }

    // Anywhere on the page, "/" jumps to the search box.
    document.addEventListener("keydown", function (event) {
        if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) {
            return;
        }
        var tag = (document.activeElement || {}).tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
            return;
        }
        event.preventDefault();
        input.focus();
        input.select();
    });
})();
