-- Nightfall Premium UI
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts.
-- The server is authoritative for Premium ownership and entitlements.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local MarketplaceService = game:GetService("MarketplaceService")
local TweenService = game:GetService("TweenService")

local player = Players.LocalPlayer
local remotes = ReplicatedStorage:WaitForChild("NightfallPremium")
local linkFunction = remotes:WaitForChild("LinkAccount")
local statusFunction = remotes:WaitForChild("GetStatus")
local redeemFunction = remotes:WaitForChild("RedeemCode")
local dailyRewardFunction = remotes:WaitForChild("ClaimDailyReward")
local purchaseEvent = remotes:WaitForChild("PremiumPurchase")

local FULL_PREMIUM_PASS_ID = 1747241092
local DISCOUNT_PREMIUM_PASS_ID = 1744202935

local gui = Instance.new("ScreenGui")
gui.Name = "NightfallPremiumUI"
gui.ResetOnSpawn = false
gui.IgnoreGuiInset = true
gui.Parent = player:WaitForChild("PlayerGui")

local open = Instance.new("TextButton")
open.Name = "PremiumButton"
open.Size = UDim2.fromOffset(150, 48)
open.Position = UDim2.new(1, -170, 0, 24)
open.BackgroundColor3 = Color3.fromRGB(24, 27, 40)
open.Text = "NIGHTFALL PREMIUM"
open.TextColor3 = Color3.fromRGB(255,255,255)
open.TextSize = 12
open.Font = Enum.Font.GothamBold
open.BorderSizePixel = 0
open.Parent = gui
Instance.new("UICorner", open).CornerRadius = UDim.new(0, 12)

local panel = Instance.new("Frame")
panel.Name = "PremiumPanel"
panel.Size = UDim2.fromOffset(430, 770)
panel.Position = UDim2.new(1, 20, 0.5, -385)
panel.BackgroundColor3 = Color3.fromRGB(9, 11, 18)
panel.BackgroundTransparency = 0.02
panel.BorderSizePixel = 0
panel.Parent = gui
Instance.new("UICorner", panel).CornerRadius = UDim.new(0, 20)

local stroke = Instance.new("UIStroke")
stroke.Color = Color3.fromRGB(104, 84, 255)
stroke.Transparency = 0.35
stroke.Thickness = 1.5
stroke.Parent = panel

local title = Instance.new("TextLabel")
title.Size = UDim2.new(1, -70, 0, 38)
title.Position = UDim2.fromOffset(20, 18)
title.BackgroundTransparency = 1
title.Text = "NIGHTFALL PREMIUM"
title.TextColor3 = Color3.fromRGB(255,255,255)
title.TextSize = 23
title.Font = Enum.Font.GothamBold
title.TextXAlignment = Enum.TextXAlignment.Left
title.Parent = panel

local close = Instance.new("TextButton")
close.Size = UDim2.fromOffset(34, 34)
close.Position = UDim2.new(1, -52, 0, 18)
close.BackgroundColor3 = Color3.fromRGB(28, 31, 45)
close.Text = "X"
close.TextColor3 = Color3.fromRGB(220,220,230)
close.TextSize = 14
close.Font = Enum.Font.GothamBold
close.BorderSizePixel = 0
close.Parent = panel
Instance.new("UICorner", close).CornerRadius = UDim.new(0, 10)

local status = Instance.new("TextLabel")
status.Size = UDim2.new(1, -40, 0, 42)
status.Position = UDim2.fromOffset(20, 62)
status.BackgroundTransparency = 1
status.Text = "Checking Premium status..."
status.TextColor3 = Color3.fromRGB(190,195,210)
status.TextSize = 13
status.Font = Enum.Font.Gotham
status.TextWrapped = true
status.TextXAlignment = Enum.TextXAlignment.Left
status.Parent = panel

local function makeButton(name, text, y, height)
	local button = Instance.new("TextButton")
	button.Name = name
	button.Size = UDim2.new(1, -40, 0, height or 44)
	button.Position = UDim2.fromOffset(20, y)
	button.BackgroundColor3 = Color3.fromRGB(104, 84, 255)
	button.Text = text
	button.TextColor3 = Color3.fromRGB(255,255,255)
	button.TextSize = 14
	button.Font = Enum.Font.GothamBold
	button.BorderSizePixel = 0
	button.Parent = panel
	Instance.new("UICorner", button).CornerRadius = UDim.new(0, 12)
	return button
end

local buyFull = makeButton("BuyPremium", "GET PREMIUM — 179 ROBUX", 112, 46)
local buyOffer = makeButton("ArcadeOffer", "ARCADE OFFER — 70 ROBUX", 166, 46)
buyOffer.Visible = false

local badge = Instance.new("TextLabel")
badge.Size = UDim2.fromOffset(118, 28)
badge.Position = UDim2.new(1, -138, 0, 70)
badge.BackgroundColor3 = Color3.fromRGB(104, 84, 255)
badge.Text = "✦ PREMIUM"
badge.TextColor3 = Color3.fromRGB(255,255,255)
badge.TextSize = 11
badge.Font = Enum.Font.GothamBold
badge.BorderSizePixel = 0
badge.Visible = false
badge.Parent = panel
Instance.new("UICorner", badge).CornerRadius = UDim.new(0, 10)

local features = Instance.new("TextLabel")
features.Size = UDim2.new(1, -40, 0, 150)
features.Position = UDim2.fromOffset(20, 222)
features.BackgroundColor3 = Color3.fromRGB(18, 21, 32)
features.BackgroundTransparency = 0.15
features.BorderSizePixel = 0
features.Text = "PREMIUM VAULT UNLOCKS\n\n🎨 Custom themes + UI colors\n🤖 AI features + 8 Ball\n✦ Premium badge + name effects\n🌌 Space backgrounds + profile effects\n🎁 Daily rewards + extra arcade rewards\n🏆 Premium titles + leaderboard badge\n⚡ Early access + Premium Vault"
features.TextColor3 = Color3.fromRGB(205,208,220)
features.TextSize = 12
features.Font = Enum.Font.Gotham
features.TextWrapped = true
features.TextXAlignment = Enum.TextXAlignment.Left
features.TextYAlignment = Enum.TextYAlignment.Top
features.Parent = panel
Instance.new("UICorner", features).CornerRadius = UDim.new(0, 14)

local customize = makeButton("Customize", "OPEN CUSTOMIZATION", 384, 42)
local daily = makeButton("DailyReward", "CLAIM DAILY REWARD", 434, 42)
local eight = makeButton("EightBall", "ASK 8 BALL", 484, 42)

local codeTitle = Instance.new("TextLabel")
codeTitle.Size = UDim2.new(1, -40, 0, 24)
codeTitle.Position = UDim2.fromOffset(20, 538)
codeTitle.BackgroundTransparency = 1
codeTitle.Text = "REDEEM STARTED — 3 MONTHS FREE PREMIUM"
codeTitle.TextColor3 = Color3.fromRGB(255,255,255)
codeTitle.TextSize = 12
codeTitle.Font = Enum.Font.GothamBold
codeTitle.TextXAlignment = Enum.TextXAlignment.Left
codeTitle.Parent = panel

local codeBox = Instance.new("TextBox")
codeBox.Size = UDim2.new(1, -140, 0, 42)
codeBox.Position = UDim2.fromOffset(20, 568)
codeBox.BackgroundColor3 = Color3.fromRGB(22, 25, 37)
codeBox.PlaceholderText = "Enter started"
codeBox.Text = ""
codeBox.TextColor3 = Color3.fromRGB(255,255,255)
codeBox.PlaceholderColor3 = Color3.fromRGB(115,120,135)
codeBox.TextSize = 14
codeBox.Font = Enum.Font.GothamMedium
codeBox.ClearTextOnFocus = false
codeBox.BorderSizePixel = 0
codeBox.Parent = panel
Instance.new("UICorner", codeBox).CornerRadius = UDim.new(0, 11)

local redeem = makeButton("Redeem", "REDEEM", 568, 42)
redeem.Size = UDim2.fromOffset(100, 42)
redeem.Position = UDim2.new(1, -120, 0, 568)

local linkBox = Instance.new("TextBox")
linkBox.Size = UDim2.new(1, -140, 0, 42)
linkBox.Position = UDim2.fromOffset(20, 618)
linkBox.BackgroundColor3 = Color3.fromRGB(22, 25, 37)
linkBox.PlaceholderText = "Website link code"
linkBox.Text = ""
linkBox.TextColor3 = Color3.fromRGB(255,255,255)
linkBox.PlaceholderColor3 = Color3.fromRGB(115,120,135)
linkBox.TextSize = 14
linkBox.Font = Enum.Font.GothamMedium
linkBox.ClearTextOnFocus = false
linkBox.BorderSizePixel = 0
linkBox.Parent = panel
Instance.new("UICorner", linkBox).CornerRadius = UDim.new(0, 11)

local link = makeButton("Link", "LINK", 618, 42)
link.Size = UDim2.fromOffset(100, 42)
link.Position = UDim2.new(1, -120, 0, 618)

local hint = Instance.new("TextLabel")
hint.Size = UDim2.new(1, -40, 0, 48)
hint.Position = UDim2.fromOffset(20, 672)
hint.BackgroundTransparency = 1
hint.Text = "The 70 Robux offer stays hidden until the arcade reward has been unlocked.\nUse the website to generate your account-link code."
hint.TextColor3 = Color3.fromRGB(125,130,145)
hint.TextSize = 11
hint.Font = Enum.Font.Gotham
hint.TextWrapped = true
hint.TextXAlignment = Enum.TextXAlignment.Left
hint.Parent = panel

local function setStatus(text, good)
	status.Text = text
	status.TextColor3 = good and Color3.fromRGB(90,230,150) or Color3.fromRGB(190,195,210)
end

local function showPanel()
	panel.Visible = true
	TweenService:Create(panel, TweenInfo.new(0.25, Enum.EasingStyle.Quart, Enum.EasingDirection.Out), {
		Position = UDim2.new(1, -450, 0.5, -385)
	}):Play()
end

local function hidePanel()
	TweenService:Create(panel, TweenInfo.new(0.2, Enum.EasingStyle.Quart, Enum.EasingDirection.In), {
		Position = UDim2.new(1, 20, 0.5, -385)
	}):Play()
end

local function refresh()
	local ok, data = pcall(function()
		return statusFunction:InvokeServer()
	end)

	if not ok or type(data) ~= "table" then
		setStatus("Could not check Premium status.", false)
		return
	end

	if data.premium then
		setStatus("Premium is active. Your Vault is unlocked.", true)
	else
		setStatus("Premium is not active. Buy Premium or redeem started.", false)
	end

	local offerUnlocked = data.arcadeOfferUnlocked == true or player:GetAttribute("ArcadeRewardUnlocked") == true
	buyOffer.Visible = offerUnlocked and not data.premium
	badge.Visible = data.premium == true
	daily.Visible = data.premium == true
	eight.Visible = data.premium == true
	customize.Visible = data.premium == true
end

buyFull.MouseButton1Click:Connect(function()
	MarketplaceService:PromptGamePassPurchase(player, FULL_PREMIUM_PASS_ID)
end)

buyOffer.MouseButton1Click:Connect(function()
	MarketplaceService:PromptGamePassPurchase(player, DISCOUNT_PREMIUM_PASS_ID)
end)

redeem.MouseButton1Click:Connect(function()
	local code = codeBox.Text:gsub("^%s+", ""):gsub("%s+$", "")
	if string.lower(code) ~= "started" then
		setStatus("The only Premium trial code is started.", false)
		return
	end

	redeem.Active = false
	redeem.Text = "..."
	local ok, data = pcall(function()
		return redeemFunction:InvokeServer(code)
	end)

	if ok and type(data) == "table" and data.success then
		codeBox.Text = ""
		setStatus("3 months of Premium are active. Your Vault is unlocked.", true)
	else
		setStatus((type(data) == "table" and data.error) or "Could not redeem the code.", false)
	end

	redeem.Active = true
	redeem.Text = "REDEEM"
	refresh()
end)

link.MouseButton1Click:Connect(function()
	local code = linkBox.Text:gsub("%s+", "")
	if code == "" then
		setStatus("Enter the link code from the Nightfall website.", false)
		return
	end

	link.Active = false
	link.Text = "..."
	local ok, data = pcall(function()
		return linkFunction:InvokeServer(code)
	end)

	if ok and type(data) == "table" and data.ok then
		linkBox.Text = ""
		setStatus(data.premium and "Account linked. Premium and the Vault are active." or "Account linked. Buy or redeem Premium to unlock the Vault.", data.premium)
	else
		setStatus((type(data) == "table" and data.error) or "Linking failed.", false)
	end

	link.Active = true
	link.Text = "LINK"
	refresh()
end)

purchaseEvent.OnClientEvent:Connect(function(data)
	if type(data) == "table" and data.premium then
		setStatus("Purchase confirmed. Premium and the Vault are active.", true)
	else
		refresh()
	end
end)

player:GetAttributeChangedSignal("ArcadeRewardUnlocked"):Connect(refresh)

open.MouseButton1Click:Connect(showPanel)
close.MouseButton1Click:Connect(hidePanel)

customize.MouseButton1Click:Connect(function()
	if not player:GetAttribute("NightfallPremium") then return end
	local current = player:GetAttribute("NightfallPremiumTheme") or "Midnight"
	local nextTheme = current == "Midnight" and "Nebula" or current == "Nebula" and "Solar" or "Midnight"
	player:SetAttribute("NightfallPremiumTheme", nextTheme)
	if nextTheme == "Nebula" then
		panel.BackgroundColor3 = Color3.fromRGB(18, 10, 36)
		stroke.Color = Color3.fromRGB(170, 90, 255)
	elseif nextTheme == "Solar" then
		panel.BackgroundColor3 = Color3.fromRGB(38, 24, 10)
		stroke.Color = Color3.fromRGB(255, 170, 60)
	else
		panel.BackgroundColor3 = Color3.fromRGB(9, 11, 18)
		stroke.Color = Color3.fromRGB(104, 84, 255)
	end
	setStatus("Premium theme changed to " .. nextTheme .. ".", true)
end)

daily.MouseButton1Click:Connect(function()
	daily.Active = false
	daily.Text = "CLAIMING..."
	local ok, data = pcall(function() return dailyRewardFunction:InvokeServer() end)
	if ok and type(data) == "table" and data.success then
		setStatus(data.message or "Daily Premium reward claimed!", true)
	else
		setStatus((type(data) == "table" and data.error) or "Daily reward unavailable.", false)
	end
	daily.Active = true
	daily.Text = "CLAIM DAILY REWARD"
end)

eight.MouseButton1Click:Connect(function()
	if not player:GetAttribute("NightfallPremium") then return end
	local answers = {
		"Absolutely.", "Most likely.", "The stars say yes.", "Not yet.", "Ask again later.",
		"Definitely.", "The Nightfall is uncertain.", "Yes — go for it.", "Probably not."
	}
	setStatus("8 Ball: " .. answers[math.random(1, #answers)], true)
end)

panel.Visible = false
refresh()
