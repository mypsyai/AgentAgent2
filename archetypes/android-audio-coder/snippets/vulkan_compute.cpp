/**
 * PSYAI Vulkan Compute for Android Audio DSP
 * 
 * GPU-accelerated processing for heavy parallel operations:
 * - FFT (radix-2)
 * - Convolution
 * - Spectral processing
 */

#pragma once

#include <vulkan/vulkan.h>
#include <android/log.h>
#include <vector>
#include <cstring>
#include <stdexcept>

#define VK_CHECK(x) do { \
    VkResult result = (x); \
    if (result != VK_SUCCESS) { \
        __android_log_print(ANDROID_LOG_ERROR, "VulkanCompute", \
            "Vulkan error %d at %s:%d", result, __FILE__, __LINE__); \
        throw std::runtime_error("Vulkan error"); \
    } \
} while(0)

namespace psyai::gpu {

/**
 * Minimal Vulkan compute context for audio DSP.
 */
class VulkanCompute {
public:
    VulkanCompute() {
        createInstance();
        selectPhysicalDevice();
        createDevice();
        createCommandPool();
    }
    
    ~VulkanCompute() {
        cleanup();
    }
    
    // Non-copyable
    VulkanCompute(const VulkanCompute&) = delete;
    VulkanCompute& operator=(const VulkanCompute&) = delete;

    /**
     * Create a GPU buffer with optional initial data.
     */
    VkBuffer createBuffer(VkDeviceSize size, VkBufferUsageFlags usage,
                          const void* data = nullptr) {
        VkBuffer buffer;
        VkBufferCreateInfo bufferInfo{};
        bufferInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        bufferInfo.size = size;
        bufferInfo.usage = usage;
        bufferInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        
        VK_CHECK(vkCreateBuffer(device_, &bufferInfo, nullptr, &buffer));
        
        VkMemoryRequirements memReqs;
        vkGetBufferMemoryRequirements(device_, buffer, &memReqs);
        
        VkMemoryAllocateInfo allocInfo{};
        allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        allocInfo.allocationSize = memReqs.size;
        allocInfo.memoryTypeIndex = findMemoryType(
            memReqs.memoryTypeBits,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT
        );
        
        VkDeviceMemory memory;
        VK_CHECK(vkAllocateMemory(device_, &allocInfo, nullptr, &memory));
        VK_CHECK(vkBindBufferMemory(device_, buffer, memory, 0));
        
        bufferMemory_[buffer] = memory;
        
        if (data) {
            void* mapped;
            VK_CHECK(vkMapMemory(device_, memory, 0, size, 0, &mapped));
            std::memcpy(mapped, data, size);
            vkUnmapMemory(device_, memory);
        }
        
        return buffer;
    }
    
    /**
     * Read buffer data back to CPU.
     */
    void readBuffer(VkBuffer buffer, void* dst, VkDeviceSize size) {
        auto it = bufferMemory_.find(buffer);
        if (it == bufferMemory_.end()) return;
        
        void* mapped;
        VK_CHECK(vkMapMemory(device_, it->second, 0, size, 0, &mapped));
        std::memcpy(dst, mapped, size);
        vkUnmapMemory(device_, it->second);
    }
    
    /**
     * Create compute pipeline from SPIR-V shader.
     */
    VkPipeline createComputePipeline(const uint32_t* spirv, size_t spirvSize,
                                     VkDescriptorSetLayout layout,
                                     VkPipelineLayout pipelineLayout) {
        VkShaderModule module;
        VkShaderModuleCreateInfo moduleInfo{};
        moduleInfo.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
        moduleInfo.codeSize = spirvSize;
        moduleInfo.pCode = spirv;
        
        VK_CHECK(vkCreateShaderModule(device_, &moduleInfo, nullptr, &module));
        
        VkPipelineShaderStageCreateInfo stageInfo{};
        stageInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
        stageInfo.stage = VK_SHADER_STAGE_COMPUTE_BIT;
        stageInfo.module = module;
        stageInfo.pName = "main";
        
        VkComputePipelineCreateInfo pipelineInfo{};
        pipelineInfo.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
        pipelineInfo.stage = stageInfo;
        pipelineInfo.layout = pipelineLayout;
        
        VkPipeline pipeline;
        VK_CHECK(vkCreateComputePipelines(device_, VK_NULL_HANDLE, 1, 
                                          &pipelineInfo, nullptr, &pipeline));
        
        vkDestroyShaderModule(device_, module, nullptr);
        return pipeline;
    }
    
    /**
     * Run compute shader.
     */
    void dispatch(VkPipeline pipeline, VkPipelineLayout layout,
                  VkDescriptorSet descriptorSet,
                  uint32_t groupCountX, uint32_t groupCountY = 1,
                  uint32_t groupCountZ = 1,
                  const void* pushConstants = nullptr, uint32_t pushSize = 0) {
        
        VkCommandBuffer cmd = beginSingleTimeCommands();
        
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE,
                                layout, 0, 1, &descriptorSet, 0, nullptr);
        
        if (pushConstants && pushSize > 0) {
            vkCmdPushConstants(cmd, layout, VK_SHADER_STAGE_COMPUTE_BIT,
                               0, pushSize, pushConstants);
        }
        
        vkCmdDispatch(cmd, groupCountX, groupCountY, groupCountZ);
        
        endSingleTimeCommands(cmd);
    }
    
    VkDevice device() const { return device_; }
    
private:
    VkInstance instance_ = VK_NULL_HANDLE;
    VkPhysicalDevice physicalDevice_ = VK_NULL_HANDLE;
    VkDevice device_ = VK_NULL_HANDLE;
    VkQueue computeQueue_ = VK_NULL_HANDLE;
    VkCommandPool commandPool_ = VK_NULL_HANDLE;
    uint32_t computeQueueFamily_ = 0;
    
    std::unordered_map<VkBuffer, VkDeviceMemory> bufferMemory_;
    
    void createInstance() {
        VkApplicationInfo appInfo{};
        appInfo.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
        appInfo.pApplicationName = "PSYAI Audio";
        appInfo.applicationVersion = VK_MAKE_VERSION(1, 0, 0);
        appInfo.pEngineName = "PSYAI";
        appInfo.engineVersion = VK_MAKE_VERSION(1, 0, 0);
        appInfo.apiVersion = VK_API_VERSION_1_1;
        
        VkInstanceCreateInfo createInfo{};
        createInfo.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
        createInfo.pApplicationInfo = &appInfo;
        
        VK_CHECK(vkCreateInstance(&createInfo, nullptr, &instance_));
    }
    
    void selectPhysicalDevice() {
        uint32_t count = 0;
        vkEnumeratePhysicalDevices(instance_, &count, nullptr);
        if (count == 0) throw std::runtime_error("No Vulkan devices");
        
        std::vector<VkPhysicalDevice> devices(count);
        vkEnumeratePhysicalDevices(instance_, &count, devices.data());
        physicalDevice_ = devices[0];  // Use first device
        
        // Find compute queue family
        uint32_t queueFamilyCount = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice_, &queueFamilyCount, nullptr);
        std::vector<VkQueueFamilyProperties> queueFamilies(queueFamilyCount);
        vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice_, &queueFamilyCount, 
                                                  queueFamilies.data());
        
        for (uint32_t i = 0; i < queueFamilyCount; ++i) {
            if (queueFamilies[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
                computeQueueFamily_ = i;
                break;
            }
        }
    }
    
    void createDevice() {
        float queuePriority = 1.0f;
        VkDeviceQueueCreateInfo queueInfo{};
        queueInfo.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
        queueInfo.queueFamilyIndex = computeQueueFamily_;
        queueInfo.queueCount = 1;
        queueInfo.pQueuePriorities = &queuePriority;
        
        VkDeviceCreateInfo deviceInfo{};
        deviceInfo.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
        deviceInfo.queueCreateInfoCount = 1;
        deviceInfo.pQueueCreateInfos = &queueInfo;
        
        VK_CHECK(vkCreateDevice(physicalDevice_, &deviceInfo, nullptr, &device_));
        vkGetDeviceQueue(device_, computeQueueFamily_, 0, &computeQueue_);
    }
    
    void createCommandPool() {
        VkCommandPoolCreateInfo poolInfo{};
        poolInfo.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
        poolInfo.queueFamilyIndex = computeQueueFamily_;
        poolInfo.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        
        VK_CHECK(vkCreateCommandPool(device_, &poolInfo, nullptr, &commandPool_));
    }
    
    VkCommandBuffer beginSingleTimeCommands() {
        VkCommandBufferAllocateInfo allocInfo{};
        allocInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        allocInfo.commandPool = commandPool_;
        allocInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        allocInfo.commandBufferCount = 1;
        
        VkCommandBuffer cmd;
        vkAllocateCommandBuffers(device_, &allocInfo, &cmd);
        
        VkCommandBufferBeginInfo beginInfo{};
        beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        
        vkBeginCommandBuffer(cmd, &beginInfo);
        return cmd;
    }
    
    void endSingleTimeCommands(VkCommandBuffer cmd) {
        vkEndCommandBuffer(cmd);
        
        VkSubmitInfo submitInfo{};
        submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submitInfo.commandBufferCount = 1;
        submitInfo.pCommandBuffers = &cmd;
        
        VkFence fence;
        VkFenceCreateInfo fenceInfo{};
        fenceInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        vkCreateFence(device_, &fenceInfo, nullptr, &fence);
        
        vkQueueSubmit(computeQueue_, 1, &submitInfo, fence);
        vkWaitForFences(device_, 1, &fence, VK_TRUE, UINT64_MAX);
        
        vkDestroyFence(device_, fence, nullptr);
        vkFreeCommandBuffers(device_, commandPool_, 1, &cmd);
    }
    
    uint32_t findMemoryType(uint32_t typeFilter, VkMemoryPropertyFlags properties) {
        VkPhysicalDeviceMemoryProperties memProps;
        vkGetPhysicalDeviceMemoryProperties(physicalDevice_, &memProps);
        
        for (uint32_t i = 0; i < memProps.memoryTypeCount; ++i) {
            if ((typeFilter & (1 << i)) &&
                (memProps.memoryTypes[i].propertyFlags & properties) == properties) {
                return i;
            }
        }
        throw std::runtime_error("Failed to find suitable memory type");
    }
    
    void cleanup() {
        for (auto& [buffer, memory] : bufferMemory_) {
            vkDestroyBuffer(device_, buffer, nullptr);
            vkFreeMemory(device_, memory, nullptr);
        }
        if (commandPool_) vkDestroyCommandPool(device_, commandPool_, nullptr);
        if (device_) vkDestroyDevice(device_, nullptr);
        if (instance_) vkDestroyInstance(instance_, nullptr);
    }
};

// ============================================================================
// FFT using Vulkan Compute
// ============================================================================

/**
 * GPU-accelerated FFT (radix-2, power-of-2 sizes only).
 */
class VulkanFFT {
public:
    VulkanFFT(VulkanCompute& compute, uint32_t maxSize)
        : compute_(compute), maxSize_(maxSize) {
        // Create descriptor set layout, pipeline layout, pipeline
        // (In production, load SPIR-V from assets)
    }
    
    /**
     * Perform forward FFT.
     * @param data Complex pairs [re0, im0, re1, im1, ...] length = 2*N
     * @param N FFT size (must be power of 2)
     */
    void forward(float* data, uint32_t N) {
        // Upload to GPU buffer
        // Run butterfly stages
        // Download result
    }
    
    /**
     * Perform inverse FFT.
     */
    void inverse(float* data, uint32_t N) {
        // Conjugate, forward FFT, conjugate, scale
    }

private:
    VulkanCompute& compute_;
    uint32_t maxSize_;
    VkBuffer dataBuffer_ = VK_NULL_HANDLE;
    VkPipeline pipeline_ = VK_NULL_HANDLE;
};

}  // namespace psyai::gpu
