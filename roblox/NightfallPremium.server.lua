-- Nightfall Premium entitlement system
-- Place this Script in ServerScriptService.
--
-- Permanent Premium passes:
--   Full price: 1747241092 (179 Robux)
--   Arcade offer: 1744202935 (70 Robux)
--
-- Temporary code:
--   started = 3 months of Premium
--
-- The server is authoritative: clients cannot grant themselves Premium by
-- changing UI/local values. Pass ownership is verified with MarketplaceService
-- and the temporary entitlement is stored in DataStoreService.

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local FULL_PREMIUM_PASS_ID = 1747241092
local DISCOUNT_PREMIUM_PASS_ID = 1744202935

local STARTED_CODE = "started"
local STARTED_DURATION_SECONDS = 90 * 24 * 60 * 60

local PREMIUM_STORE = DataStoreService:GetDataStore("NightfallPremium_v1")

local remotes = ReplicatedStorage:FindFirstChild("NightfallPremium")
if not remotes then
    remotes = Instance.new("Folder")
    remotes.Name = "NightfallPremium"
    remotes.Parent = ReplicatedStorage
end

local redeemFunction = remotes:FindFirstChild("RedeemCode")
if not redeemFunction then
    redeemFunction = Instance.new("RemoteFunction")
    redeemFunction.Name = "RedeemCode"
    redeemFunction.Parent = remotes
end

local statusFunction = remotes:FindFirstChild("GetStatus")
if not statusFunction then
    statusFunction = Instance.new("RemoteFunction")
    statusFunction.Name = "GetStatus"
    statusFunction.Parent = remotes
end

local purchaseEvent = remotes:FindFirstChild("PremiumPurchase")
if not purchaseEvent then
    purchaseEvent = Instance.new("RemoteEvent")
    purchaseEvent.Name = "PremiumPurchase"
    purchaseEvent.Parent = remotes
end

local cache = {}

local function getData(userId)
    local key = "user_" .. tostring(userId)
    local success, data = pcall(function()
        return PREMIUM_STORE:GetAsync(key)
    end)

    if not success then
        warn("[Nightfall Premium] Could not load entitlement:", data)
        return nil
    end

    if type(data) ~= "table" then
        data = {}
    end

    return data
end

local function saveData(userId, data)
    local key = "user_" .. tostring(userId)
    local success, err = pcall(function()
        PREMIUM_STORE:SetAsync(key, data)
    end)

    if not success then
        warn("[Nightfall Premium] Could not save entitlement:", err)
    end

    return success
end

local function ownsPass(userId, passId)
    local success, owns = pcall(function()
        return MarketplaceService:UserOwnsGamePassAsync(userId, passId)
    end)

    if not success then
        warn("[Nightfall Premium] Could not verify pass:", passId, owns)
        return false
    end

    return owns == true
end

local function hasPermanentPremium(userId)
    return ownsPass(userId, FULL_PREMIUM_PASS_ID)
        or ownsPass(userId, DISCOUNT_PREMIUM_PASS_ID)
end

local function getTemporaryExpiry(data)
    local expiresAt = tonumber(data and data.premiumExpiresAt) or 0
    if expiresAt > os.time() then
        return expiresAt
    end
    return 0
end

local function isPremium(userId)
    if hasPermanentPremium(userId) then
        return true, "pass", 0
    end

    local data = cache[userId] or getData(userId)
    if data then
        cache[userId] = data
    end

    local expiresAt = getTemporaryExpiry(data)
    if expiresAt > 0 then
        return true, "started", expiresAt
    end

    return false, "none", 0
end

local function applyPremium(player)
    local premium, source, expiresAt = isPremium(player.UserId)

    player:SetAttribute("NightfallPremium", premium)
    player:SetAttribute("NightfallPremiumSource", source)
    player:SetAttribute("NightfallPremiumExpiresAt", expiresAt)

    return premium, source, expiresAt
end

local function hasRedeemedStarted(data)
    return data and data.startedRedeemed == true
end

redeemFunction.OnServerInvoke = function(player, rawCode)
    if type(rawCode) ~= "string" then
        return { ok = false, error = "Invalid code." }
    end

    local code = string.lower(rawCode:gsub("^%s+", ""):gsub("%s+$", ""))
    if code ~= STARTED_CODE then
        return { ok = false, error = "Invalid code." }
    end

    local data = cache[player.UserId] or getData(player.UserId)
    if not data then
        return { ok = false, error = "Premium service is temporarily unavailable." }
    end

    cache[player.UserId] = data

    if hasRedeemedStarted(data) then
        return { ok = false, error = "This code has already been redeemed on your account." }
    end

    local existingExpiry = getTemporaryExpiry(data)
    local now = os.time()

    data.startedRedeemed = true
    data.startedRedeemedAt = now
    data.premiumExpiresAt = math.max(existingExpiry, now) + STARTED_DURATION_SECONDS
    data.premiumSource = "started"

    if not saveData(player.UserId, data) then
        return { ok = false, error = "Could not save the Premium entitlement. Try again." }
    end

    cache[player.UserId] = data
    local premium, source, expiresAt = applyPremium(player)

    return {
        ok = premium,
        source = source,
        expiresAt = expiresAt,
        offerUnlocked = true,
        message = "3 months of Premium have been added to your account.",
    }
end

statusFunction.OnServerInvoke = function(player)
    local premium, source, expiresAt = applyPremium(player)

    return {
        premium = premium,
        source = source,
        expiresAt = expiresAt,
        arcadeOfferUnlocked = false,
    }
end

local function onPlayerAdded(player)
    task.spawn(function()
        applyPremium(player)
    end)
end

Players.PlayerAdded:Connect(onPlayerAdded)

for _, player in ipairs(Players:GetPlayers()) do
    task.spawn(function()
        applyPremium(player)
    end)
end

MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player, gamePassId, purchased)
    if not purchased then
        return
    end

    if gamePassId == FULL_PREMIUM_PASS_ID or gamePassId == DISCOUNT_PREMIUM_PASS_ID then
        -- Roblox updates the ownership cache for this event on the server.
        applyPremium(player)
        purchaseEvent:FireClient(player, true)
    end
end)
\n-- Premium feature flags. These are authoritative server attributes; UI alone never grants access.\nlocal PREMIUM_FEATURES = {\n    Customization = true,\n    AIFeatures = true,\n    EightBall = true,\n    PremiumSpaceThemes = true,\n    ProfileEffects = true,\n    UIColors = true,\n    PremiumBadge = true,\n    NameEffects = true,\n    ChatEffects = true,\n    ExclusivePlanetBackgrounds = true,\n    PremiumDailyReward = true,\n    PremiumRewards = true,\n    ExtraArcadeRewards = true,\n    LeaderboardBadge = true,\n    PremiumTitles = true,\n    EarlyAccess = true,\n    Vault = false, -- Premium does not automatically unlock the Vault.\n}\n\nlocal function applyFeatureAttributes(player, premium)\n    for featureName, enabledForPremium in pairs(PREMIUM_FEATURES) do\n        local attributeName = "NightfallPremium_" .. featureName\n        player:SetAttribute(attributeName, premium and enabledForPremium or false)\n    end\nend\n