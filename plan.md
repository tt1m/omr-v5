# Pipeline

## 1. Template
### Json Structure
#### template.json
``` json
{
  "name": "Standard Exam Sheet",1
  "image": {
    "width": 2480,
    "height": 3508
  },
  "fields": [
    {
      "name": "class_number",
      "type": "metadata",
      "bubble": {
        "shape": "rectangle",
        "width": 14,
        "height": 14
      },
      "entries": [
        {
          "name": "digit_1",
          "bubbles": [
            { "x": 108, "y": 212, "value": "0" },
            { "x": 108, "y": 230, "value": "1" },
            { "x": 108, "y": 248, "value": "2" },
            { "x": 108, "y": 266, "value": "3" },
            { "x": 108, "y": 284, "value": "4" },
            { "x": 108, "y": 302, "value": "5" },
            { "x": 108, "y": 320, "value": "6" },
            { "x": 108, "y": 338, "value": "7" },
            { "x": 108, "y": 356, "value": "8" },
            { "x": 108, "y": 374, "value": "9" }
          ]
        }
      ]
    },
    {
      "name": "answers",
      "type": "answers",
      "bubble": {
        "shape": "rectangle",
        "width": 14,
        "height": 14
      },
      "entries": [
        {
          "question": 1,
          "bubbles": [
            { "x": 312, "y": 214, "value": "A" },
            { "x": 334, "y": 214, "value": "B" },
            { "x": 356, "y": 214, "value": "C" },
            { "x": 378, "y": 214, "value": "D" }
          ]
        },
        {
          "question": 2,
          "bubbles": [
            { "x": 312, "y": 232, "value": "A" },
            { "x": 334, "y": 232, "value": "B" },
            { "x": 356, "y": 232, "value": "C" },
            { "x": 378, "y": 232, "value": "D" }
          ]
        },
        {
          "question": 3,
          "bubbles": [
            { "x": 312, "y": 250, "value": "A" },
            { "x": 334, "y": 250, "value": "B" },
            { "x": 356, "y": 250, "value": "C" },
            { "x": 378, "y": 250, "value": "D" }
          ]
        }
      ]
    }
  ]
} 
```

**user-inputed:**
- option values
- first bubble top left
- row gaps
- col gaps
- type
- starting_question 
- bubble shape, size
- name for the section


### Frontend
MVP Functions: 
- Load your image
- Sidebar with groups and sections, with editable fields
- Bubbles will render onto the page, letting you align them
- outlines of groups and sections and stuff

Essential UX requirements:
1. History Control
   1. Undo 
   2. Redo
2. Standardized hotkeys
3. State feedback
   1. explicit visual statuses like "Saving", "Saved" etc.
4. Data safety
   1. Background autosaving

More for UX:
- allow editing directly on canvas
- allow users to move entire groups at once, or just individual sections
- multi-select if possible? 
- tooltip when hovering?
- can do some research from tools like canva and figma

Local runtime temporary storage --(when pressing save)--> save to actual .json 

### Backend
1. Loading template image
   - deskew
   - resize 
2. Building sidebar and then rendering onto the image first
3. Directly editing on canvas can be dealt with in the future

