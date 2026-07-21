//! Episteme.app — a native window over the local governance dashboard (E176).
//!
//! Deliberately thin: this shell owns exactly two jobs — ensure the viewer
//! server is running, and show it in a real window. All product logic stays
//! in `episteme viewer` (Python, stdlib-only); the shell adds no second
//! implementation of anything, so it cannot drift from the kernel.
//!
//! Lifecycle: if the viewer port already answers (operator ran `episteme
//! viewer` themselves), attach to it and spawn nothing; otherwise spawn
//! `episteme viewer --no-open` as a child and kill it on window close.

use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoop};
use tao::window::WindowBuilder;
use wry::WebViewBuilder;

const PORT: u16 = 37776;
// Worst-case blank-launch window (review): the probe runs before the window
// exists, so this bounds how long a broken viewer boot can look like a hang.
// Typical boot is ~0.1s; window-first + background probe is the deferred fix.
const SPAWN_WAIT: Duration = Duration::from_secs(6);

fn port_open() -> bool {
    TcpStream::connect_timeout(
        &([127, 0, 0, 1], PORT).into(),
        Duration::from_millis(250),
    )
    .is_ok()
}

/// Locate the `episteme` CLI: explicit override, then PATH, then the
/// well-known install prefixes a .pkg user is likely to have (GUI apps do
/// not inherit a login shell's PATH, so PATH alone is not enough).
fn episteme_bin() -> Option<String> {
    if let Ok(bin) = std::env::var("EPISTEME_BIN") {
        if std::path::Path::new(&bin).exists() {
            return Some(bin);
        }
    }
    if let Ok(out) = Command::new("/usr/bin/which").arg("episteme").output() {
        let path = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if !path.is_empty() {
            return Some(path);
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    for candidate in [
        format!("{home}/miniconda3/bin/episteme"),
        "/Library/Frameworks/Python.framework/Versions/3.11/bin/episteme".into(),
        "/usr/local/bin/episteme".into(),
        "/opt/homebrew/bin/episteme".into(),
    ] {
        if std::path::Path::new(&candidate).exists() {
            return Some(candidate);
        }
    }
    None
}

fn spawn_viewer() -> Result<Child, String> {
    let bin = episteme_bin().ok_or(
        "episteme CLI not found (set EPISTEME_BIN or install the package)",
    )?;
    Command::new(bin)
        .args([
            "viewer",
            "--no-open",
            "--exit-with-parent",
            "--port",
            &PORT.to_string(),
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("failed to spawn episteme viewer: {e}"))
}

fn main() {
    // Attach-or-spawn: an already-running viewer is respected, not duplicated.
    let mut child: Option<Child> = None;
    let mut error: Option<String> = None;
    if !port_open() {
        match spawn_viewer() {
            Ok(c) => {
                child = Some(c);
                let deadline = Instant::now() + SPAWN_WAIT;
                while !port_open() && Instant::now() < deadline {
                    std::thread::sleep(Duration::from_millis(200));
                }
                if !port_open() {
                    error = Some("viewer did not answer within 15s".into());
                }
            }
            Err(e) => error = Some(e),
        }
    }

    let event_loop = EventLoop::new();
    let window = WindowBuilder::new()
        .with_title("Episteme")
        .with_inner_size(tao::dpi::LogicalSize::new(1280.0, 860.0))
        .build(&event_loop)
        .expect("window");

    // On failure, render the reason instead of a dead white page — the shell
    // must never look healthier than the system it fronts.
    let url = format!("http://127.0.0.1:{PORT}/");
    let builder = match &error {
        None => WebViewBuilder::new().with_url(&url),
        Some(raw) => {
            let msg = raw.replace('<', "&lt;").replace('>', "&gt;");
            WebViewBuilder::new().with_html(format!(
                "<body style=\"background:#0b0e14;color:#e06c75;font:14px monospace;\
                 padding:40px\"><h2>episteme viewer unavailable</h2><p>{}</p>\
                 <p style=\"color:#7a8494\">Start it manually: <code>episteme \
                 viewer</code>, then relaunch this app.</p></body>",
                msg
            ))
        }
    };
    let _webview = builder.build(&window).expect("webview");

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        if let Event::WindowEvent {
            event: WindowEvent::CloseRequested,
            ..
        } = event
        {
            // Kill only what we spawned; an attached external viewer stays up.
            if let Some(c) = child.as_mut() {
                let _ = c.kill();
                let _ = c.wait();
            }
            *control_flow = ControlFlow::Exit;
        }
    });
}
