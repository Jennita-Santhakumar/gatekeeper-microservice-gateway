import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "./LoginForm";
import * as api from "../lib/api";

describe("LoginForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls onSuccess after a successful login", async () => {
    vi.spyOn(api, "login").mockResolvedValue({ access_token: "tok", token_type: "bearer" });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<LoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "hunter2");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("shows an error message when login fails", async () => {
    vi.spyOn(api, "login").mockRejectedValue(new api.ApiError(401, "Invalid credentials"));
    const user = userEvent.setup();

    render(<LoginForm onSuccess={vi.fn()} />);
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });
});
