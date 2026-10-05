-- Nightfall Premium client UI
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts.
-- The server remains authoritative; this only provides the linking UI.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local player = Players.LocalPlayer
local remotes = ReplicatedStorage:WaitForChild("NightfallPremium")
local linkFunction = remotes:WaitForChild("LinkAccount")
local statusFunction = remotes:WaitForChild("GetStatus")
local purchaseEvent = remotes:WaitForChild("PremiumPurchase")

local gui = Instance.new("ScreenGui")
gui.Name = "NightfallPremiumUI"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local panel = Instance.new("Frame")
panel.Size = UDim2.fromOffset(360, 190)
panel.Position = UDim2.new(1, -380, 1, -210)
panel.BackgroundColor3 = Color3.fromRGB(13, 15, 23)
panel.BackgroundTransparency = 0.06
panel.BorderSizePixel = 0
panel.Parent = gui

local corner = Instance.new("UICorner")
corner.CornerRadius = UDim.new(0, 16)
corner.Parent = panel

local title = Instance.new("TextLabel")
title.Size = UDim2.new(1, -30, 0, 30)
title.Position = UDim2.fromOffset(15, 12)
title.BackgroundTransparency = 1
title.Text = "NIGHTFALL PREMIUM"
title.TextColor3 = Color3.fromRGB(255,255,255)
title.TextSize = 18
title.Font = Enum.Font.GothamBold
title.TextXAlignment = Enum.TextXAlignment.Left
title.Parent = panel

local status = Instance.new("TextLabel")
status.Size = UDim2.new(1, -30, 0, 42)
status.Position = UDim2.fromOffset(15, 45)
status.BackgroundTransparency = 1
status.Text = "Checking Premium status..."
status.TextColor3 = Color3.fromRGB(190,195,210)
status.TextSize = 13
status.Font = Enum.Font.Gotham
status.TextWrapped = true
status.TextXAlignment = Enum.TextXAlignment.Left
status.Parent = panel

local input = Instance.new("TextBox")
input.Size = UDim2.new(1, -140, 0, 42)
input.Position = UDim2.fromOffset(15, 100)
input.BackgroundColor3 = Color3.fromRGB(25, 29, 42)
input.BorderSizePixel = 0
input.PlaceholderText = "Website link code"
input.Text = ""
input.TextColor3 = Color3.fromRGB(255,255,255)
input.PlaceholderColor3 = Color3.fromRGB(120,125,140)
input.TextSize = 14
input.Font = Enum.Font.GothamMedium
input.ClearTextOnFocus = false
input.Parent = panel

local inputCorner = Instance.new("UICorner")
inputCorner.CornerRadius = UDim.new(0, 10)
inputCorner.Parent = input

local link = Instance.new("TextButton")
link.Size = UDim2.fromOffset(105, 42)
link.Position = UDim2.new(1, -120, 0, 100)
link.BackgroundColor3 = Color3.fromRGB(104, 84, 255)
link.BorderSizePixel = 0
link.Text = "LINK"
link.TextColor3 = Color3.fromRGB(255,255,255)
link.TextSize = 14
link.Font = Enum.Font.GothamBold
link.Parent = panel

local linkCorner = Instance.new("UICorner")
linkCorner.CornerRadius = UDim.new(0, 10)
linkCorner.Parent = link

local hint = Instance.new("TextLabel")
hint.Size = UDim2.new(1, -30, 0, 30)
hint.Position = UDim2.fromOffset(15, 150)
hint.BackgroundTransparency = 1
hint.Text = "Generate the code on the Nightfall website."
hint.TextColor3 = Color3.fromRGB(125,130,145)
hint.TextSize = 11
hint.Font = Enum.Font.Gotham
hint.TextXAlignment = Enum.TextXAlignment.Left
hint.Parent = panel

local function refresh()
	local ok, data = pcall(function()
		return statusFunction:InvokeServer()
	end)
	if ok and type(data) == "table" and data.premium then
		status.Text = "Premium is active. Your Vault is unlocked."
		status.TextColor3 = Color3.fromRGB(90, 230, 150)
	elseif ok then
		status.Text = "Premium is not active yet. Link your website account after buying or redeeming Premium."
		status.TextColor3 = Color3.fromRGB(190,195,210)
	else
		status.Text = "Could not check Premium status."
	end
end

link.MouseButton1Click:Connect(function()
	local code = input.Text:gsub("%s+", "")
	if code == "" then
		status.Text = "Enter the link code from the website."
		return
	end

	link.Active = false
	link.Text = "..."
	local ok, data = pcall(function()
		return linkFunction:InvokeServer(code)
	end)

	if ok and type(data) == "table" and data.ok then
		input.Text = ""
		status.Text = data.premium and "Account linked. Premium and the Vault are active." or "Account linked. Buy or redeem Premium to unlock the Vault."
		status.TextColor3 = data.premium and Color3.fromRGB(90,230,150) or Color3.fromRGB(190,195,210)
	else
		status.Text = (type(data) == "table" and data.error) or "Linking failed."
		status.TextColor3 = Color3.fromRGB(255,120,120)
	end

	link.Active = true
	link.Text = "LINK"
end)

purchaseEvent.OnClientEvent:Connect(function()
	refresh()
end)

refresh()
