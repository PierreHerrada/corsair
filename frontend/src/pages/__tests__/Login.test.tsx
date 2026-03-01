import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "../Login";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockSetItem = vi.fn();
Object.defineProperty(globalThis, "localStorage", {
  value: {
    getItem: vi.fn(),
    setItem: mockSetItem,
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(),
  },
  writable: true,
});

describe("Login", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    mockSetItem.mockClear();
  });

  it("renders the login form", () => {
    render(<Login />);
    expect(screen.getByText("corsair")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter password")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  it("stores password and navigates on submit", () => {
    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Enter password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByText("Sign In"));
    expect(mockSetItem).toHaveBeenCalledWith("corsair_auth", "secret123");
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("shows error when password is empty", () => {
    render(<Login />);
    fireEvent.click(screen.getByText("Sign In"));
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("renders the Corsair logo", () => {
    render(<Login />);
    const logo = screen.getByAltText("Corsair");
    expect(logo).toBeInTheDocument();
  });
});
