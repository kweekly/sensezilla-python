// from http://stackoverflow.com/questions/11673591/how-would-you-create-a-jquery-svg-click-drag-select-outline-effect

(function createMarquee(global){
  var svgNS = 'http://www.w3.org/2000/svg',
      svg   = document.createElementNS(svgNS,'svg'),
      pt    = svg.createSVGPoint();

  global.trackMarquee = function(forElement,onRelease,onDrag){
    forElement.addEventListener('mousedown',function(evt){
      var point0 = getLocalCoordinatesFromMouseEvent(forElement,evt);
      var marquee = document.createElementNS(svgNS,'rect');
      marquee.setAttribute('class','marquee');
      updateMarquee(marquee,point0,point0);
      forElement.appendChild(marquee);
      document.documentElement.addEventListener('mousemove',trackMouseMove,false);
      document.documentElement.addEventListener('mouseup',stopTrackingMove,false);
      function trackMouseMove(evt){
        var point1 = getLocalCoordinatesFromMouseEvent(forElement,evt);
        updateMarquee(marquee,point0,point1);
        if (onDrag) callWithBBox(onDrag,marquee);
      }
      function stopTrackingMove(){
        document.documentElement.removeEventListener('mousemove',trackMouseMove,false);
        document.documentElement.removeEventListener('mouseup',stopTrackingMove,false);
        forElement.removeChild(marquee);
        if (onRelease) callWithBBox(onRelease,marquee);
      }
    },false);
  };

  function callWithBBox(func,rect){
    var x = rect.getAttribute('x')*1,
        y = rect.getAttribute('y')*1,
        w = rect.getAttribute('width')*1,
        h = rect.getAttribute('height')*1;
    func(x,y,x+w,y+h);
  }

  function updateMarquee(rect,p0,p1){
    var xs = [p0.x,p1.x].sort(sortByNumber),
        ys = [p0.y,p1.y].sort(sortByNumber);
    rect.setAttribute('x',xs[0]);
    rect.setAttribute('y',ys[0]);
    rect.setAttribute('width', xs[1]-xs[0]);
    rect.setAttribute('height',ys[1]-ys[0]);
  }

  function getLocalCoordinatesFromMouseEvent(el,evt){
    pt.x = evt.clientX; pt.y = evt.clientY;
    return pt.matrixTransform(el.getScreenCTM().inverse());
  }

  function sortByNumber(a,b){ return a-b }
})(window);


