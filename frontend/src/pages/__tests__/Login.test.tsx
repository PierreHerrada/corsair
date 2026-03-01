import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockLogin = vi.fn();
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ login: mockLogin }),
}));

import Login from "../Login";

describe("Login", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    mockLogin.mockClear();
  });

  it("renders the login form", () => {
    render(<Login />);
    expect(screen.getByText("corsair")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter password")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  it("calls login API and navigates on success", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Enter password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByText("Sign In"));
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("secret123");
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
  });

  it("shows error when password is empty", () => {
    render(<Login />);
    fireEvent.click(screen.getByText("Sign In"));
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("shows server error on login failure", async () => {
    mockLogin.mockRejectedValueOnce(new Error("Invalid password"));
    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Enter password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByText("Sign In"));
    await waitFor(() => {
      expect(screen.getByText("Invalid password")).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("shows loading state while logging in", async () => {
    let resolve: () => void;
    const promise = new Promise<void>((r) => {
      resolve = r;
    });
    mockLogin.mockReturnValueOnce(promise);
    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Enter password"), {
      target: { value: "test" },
    });
    fireEvent.click(screen.getByText("Sign In"));
    expect(screen.getByText("Signing in...")).toBeInTheDocument();
    resolve!();
    await waitFor(() => {
      expect(screen.getByText("Sign In")).toBeInTheDocument();
    });
  });

  it("renders the Corsair logo", () => {
    render(<Login />);
    const logo = screen.getByAltText("Corsair");
    expect(logo).toBeInTheDocument();
  });
});
