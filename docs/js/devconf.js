(function ($) {
  $(document).ready(function(){

<<<<<<< HEAD
  // hide .navbar first
  $(".navbar").hide();

  // get logo distance from top
  logo_pos = $("#devconf-logo").offset().top - $("#page-top").offset().top

  // user can load already scrolled page (eg. refreshing, ...); check it even on document ready
  if ($(this).scrollTop() > logo_pos) {
    $('.navbar').fadeIn();
  } else {
    $('.navbar').fadeOut();
  }

  // hook on scroll and show/hide navbar
=======
  // FIXME: if page is refreshed while lower at the bottom of the page the navbar does appear...
  // eg, load page, scroll down (navbar appears), CTRL-R... navbar remains hidden even though
  // we are far down the page
  // hide .navbar first
  $(".navbar").hide();

  // fade in .navbar
>>>>>>> 5d752f56334ffc788db5b0c23cba9180680178f3
  $(function () {
    $(window).scroll(function () {
      // set distance user needs to scroll before we fadeIn navbar
      // FIXME: Make this START at the ABOUT page
<<<<<<< HEAD
=======
      logo_pos = $("#devconf-logo").offset().top - $("#page-top").offset().top
>>>>>>> 5d752f56334ffc788db5b0c23cba9180680178f3
      if ($(this).scrollTop() > logo_pos) {
        $('.navbar').fadeIn();
      } else {
        $('.navbar').fadeOut();
      }
    });


  });

});
  }(jQuery));
